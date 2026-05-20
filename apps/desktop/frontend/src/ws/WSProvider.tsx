/**
 * `WSProvider` — React context wrapping a `/ws` connection.
 *
 * Responsibilities:
 *
 * - Open a connection on mount via the injected `socketFactory`.
 * - Auto-reconnect with jittered exponential backoff via
 *   `createReconnectController`.
 * - Decode every inbound message string into a typed `ServerMessage`
 *   and expose it both as `lastMessage` and through a per-type
 *   subscription API (`subscribe("avatar.directive", handler)`).
 * - Provide `send(msg: ClientMessage)` that serialises to JSON.
 *
 * The factory is pluggable so tests can supply a `MockWebSocket`.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import { createReconnectController, type ReconnectConfig } from "./reconnect";
import {
  isServerMessage,
  type ClientMessage,
  type ServerMessage,
  type ServerMessageType,
} from "./protocol";
import type { WebSocketLike } from "./mockSocket";

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

export type ConnectionStatus = "idle" | "connecting" | "open" | "closed";

type Listener<T extends ServerMessageType> = (
  msg: Extract<ServerMessage, { type: T }>,
) => void;

export interface WSContextValue {
  status: ConnectionStatus;
  lastMessage: ServerMessage | null;
  send(message: ClientMessage): void;
  /**
   * Subscribe to one message type. Returns the unsubscribe function.
   * Strictly typed: handler receives the narrowed variant.
   */
  subscribe<T extends ServerMessageType>(
    type: T,
    handler: Listener<T>,
  ): () => void;
  /** Force a reconnect (closes the current socket if open). Useful from tests. */
  reconnect(): void;
}

const noop = (): void => {};

const DEFAULT_CONTEXT: WSContextValue = {
  status: "idle",
  lastMessage: null,
  send: noop,
  subscribe: () => noop,
  reconnect: noop,
};

const WSContext = createContext<WSContextValue>(DEFAULT_CONTEXT);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export type SocketFactory = (url: string) => WebSocketLike;

export interface WSProviderProps extends PropsWithChildren {
  /** WS URL. Defaults to `${origin.replace(/^http/, "ws")}/ws`. */
  url?: string;
  /** Pluggable socket factory (tests inject `mockSocketFactory().factory`). */
  socketFactory?: SocketFactory;
  /** Reconnect tunables. */
  reconnect?: ReconnectConfig;
  /** Set to false to skip the initial connect (lets tests stage state). */
  autoConnect?: boolean;
}

function defaultUrl(): string {
  if (typeof window === "undefined") return "ws://localhost:8000/ws";
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws`;
}

function defaultFactory(url: string): WebSocketLike {
  // The browser global has a wider type than our shrunk-down interface,
  // but every method we use is present on it.
  return new WebSocket(url) as unknown as WebSocketLike;
}

export function WSProvider(props: WSProviderProps): JSX.Element {
  const {
    url = defaultUrl(),
    socketFactory = defaultFactory,
    reconnect: reconnectCfg,
    autoConnect = true,
    children,
  } = props;

  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [lastMessage, setLastMessage] = useState<ServerMessage | null>(null);

  // The current socket is mutable across renders; the reconnect loop
  // closes around `socketRef.current`.
  const socketRef = useRef<WebSocketLike | null>(null);
  const listenersRef = useRef<Map<ServerMessageType, Set<Listener<ServerMessageType>>>>(
    new Map(),
  );
  const ctrlRef = useRef(createReconnectController(reconnectCfg));
  const stoppedRef = useRef(false);
  const forceReconnectRef = useRef<(() => void) | null>(null);

  // -----------------------------------------------------------------------
  // Connection lifecycle
  // -----------------------------------------------------------------------

  const connect = useCallback(() => {
    if (stoppedRef.current) return;
    setStatus("connecting");
    const ws = socketFactory(url);
    socketRef.current = ws;

    const onOpen = (): void => {
      ctrlRef.current.reset();
      setStatus("open");
    };

    const onMessage = (ev: Event): void => {
      const data = (ev as unknown as { data?: string }).data;
      if (typeof data !== "string") return;
      let parsed: unknown;
      try {
        parsed = JSON.parse(data);
      } catch {
        return;
      }
      if (!isServerMessage(parsed)) return;
      const msg = parsed;
      setLastMessage(msg);
      const bucket = listenersRef.current.get(msg.type);
      if (!bucket) return;
      for (const fn of Array.from(bucket)) {
        try {
          (fn as Listener<typeof msg.type>)(
            msg as Extract<ServerMessage, { type: typeof msg.type }>,
          );
        } catch {
          // listener errors are swallowed; one broken consumer doesn't
          // poison the dispatch loop.
        }
      }
    };

    const onClose = (): void => {
      setStatus("closed");
      socketRef.current = null;
      if (stoppedRef.current) return;
      void scheduleReconnect();
    };

    const onError = (): void => {
      // Errors land as `close` on most browsers; some send `error`
      // separately. We rely on `close` to drive reconnect.
    };

    ws.addEventListener("open", onOpen);
    ws.addEventListener("message", onMessage);
    ws.addEventListener("close", onClose);
    ws.addEventListener("error", onError);
    // eslint-disable-next-line @typescript-eslint/no-unused-expressions
    void onError;
  }, [socketFactory, url]);

  const scheduleReconnect = useCallback(async (): Promise<void> => {
    if (stoppedRef.current) return;
    if (!ctrlRef.current.hasAttemptsLeft()) return;
    await ctrlRef.current.wait();
    if (stoppedRef.current) return;
    connect();
  }, [connect]);

  const forceReconnect = useCallback((): void => {
    const ws = socketRef.current;
    if (ws) {
      try {
        ws.close();
      } catch {
        // ignore
      }
    } else {
      void scheduleReconnect();
    }
  }, [scheduleReconnect]);
  forceReconnectRef.current = forceReconnect;

  // -----------------------------------------------------------------------
  // Mount / unmount
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (!autoConnect) return;
    stoppedRef.current = false;
    connect();
    return () => {
      stoppedRef.current = true;
      const ws = socketRef.current;
      socketRef.current = null;
      if (ws) {
        try {
          ws.close();
        } catch {
          // ignore
        }
      }
    };
  }, [autoConnect, connect]);

  // -----------------------------------------------------------------------
  // Public API
  // -----------------------------------------------------------------------

  const send = useCallback((message: ClientMessage): void => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== 1) {
      // Drop messages sent while the socket isn't open. The frontend is
      // optimistic about reconnects; the user can retry once `status`
      // returns to "open".
      return;
    }
    try {
      ws.send(JSON.stringify(message));
    } catch {
      // ignore — `close` will fire and trigger a reconnect.
    }
  }, []);

  const subscribe = useCallback(
    <T extends ServerMessageType>(type: T, handler: Listener<T>): (() => void) => {
      const bucket =
        listenersRef.current.get(type) ?? new Set<Listener<ServerMessageType>>();
      bucket.add(handler as Listener<ServerMessageType>);
      listenersRef.current.set(type, bucket);
      return () => {
        const b = listenersRef.current.get(type);
        if (!b) return;
        b.delete(handler as Listener<ServerMessageType>);
        if (b.size === 0) listenersRef.current.delete(type);
      };
    },
    [],
  );

  const value = useMemo<WSContextValue>(
    () => ({
      status,
      lastMessage,
      send,
      subscribe,
      reconnect: () => forceReconnectRef.current?.(),
    }),
    [status, lastMessage, send, subscribe],
  );

  return <WSContext.Provider value={value}>{children}</WSContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useWS(): WSContextValue {
  return useContext(WSContext);
}

export { WSContext };
