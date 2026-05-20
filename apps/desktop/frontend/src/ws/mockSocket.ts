/**
 * MockWebSocket — a deterministic stand-in for tests.
 *
 * Behaves like the browser `WebSocket` interface used by `WSProvider`:
 * `OPEN`/`CLOSED` readyState transitions, `addEventListener` for
 * `"open" | "message" | "close" | "error"`, `send`, and `close`.
 * Tests drive the socket through `_dispatchMessage` (server -> client)
 * and inspect `sent` (client -> server).
 */

export type ListenerName = "open" | "message" | "close" | "error";

export interface WebSocketLike {
  readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  addEventListener(name: ListenerName, listener: EventListener): void;
  removeEventListener(name: ListenerName, listener: EventListener): void;
}

const CONNECTING = 0;
const OPEN = 1;
const CLOSING = 2;
const CLOSED = 3;

export class MockWebSocket implements WebSocketLike {
  static readonly CONNECTING = CONNECTING;
  static readonly OPEN = OPEN;
  static readonly CLOSING = CLOSING;
  static readonly CLOSED = CLOSED;

  public readyState: number = CONNECTING;
  public readonly url: string;
  public sent: string[] = [];

  private listeners: Record<ListenerName, EventListener[]> = {
    open: [],
    message: [],
    close: [],
    error: [],
  };

  constructor(url: string) {
    this.url = url;
    // Auto-open on next microtask so callers can attach listeners first.
    queueMicrotask(() => this._open());
  }

  send(data: string): void {
    if (this.readyState !== OPEN) {
      throw new Error("MockWebSocket: send while not OPEN");
    }
    this.sent.push(data);
  }

  close(code = 1000, reason = ""): void {
    if (this.readyState === CLOSED) return;
    this.readyState = CLOSED;
    this._fire("close", new CloseEventStub(code, reason));
  }

  addEventListener(name: ListenerName, listener: EventListener): void {
    this.listeners[name].push(listener);
  }

  removeEventListener(name: ListenerName, listener: EventListener): void {
    this.listeners[name] = this.listeners[name].filter((l) => l !== listener);
  }

  // ----- test-only hooks -----------------------------------------------------

  _open(): void {
    if (this.readyState === OPEN) return;
    this.readyState = OPEN;
    this._fire("open", new Event("open"));
  }

  _dispatchMessage(payload: unknown): void {
    const data = typeof payload === "string" ? payload : JSON.stringify(payload);
    this._fire("message", new MessageEventStub(data));
  }

  _serverClose(code = 1006, reason = "server-initiated"): void {
    this.readyState = CLOSED;
    this._fire("close", new CloseEventStub(code, reason));
  }

  private _fire(name: ListenerName, event: Event): void {
    for (const fn of this.listeners[name].slice()) {
      try {
        fn(event);
      } catch {
        // Swallow listener errors so one bad listener doesn't break the rest.
      }
    }
  }
}

// jsdom doesn't expose CloseEvent / MessageEvent constructors reliably,
// so we ship tiny stubs.

class MessageEventStub extends Event {
  public data: string;
  constructor(data: string) {
    super("message");
    this.data = data;
  }
}

class CloseEventStub extends Event {
  public code: number;
  public reason: string;
  public wasClean: boolean;
  constructor(code: number, reason: string) {
    super("close");
    this.code = code;
    this.reason = reason;
    this.wasClean = code === 1000;
  }
}

/** Factory matching the `WSProvider` socket-factory signature. */
export function mockSocketFactory(): { factory: (url: string) => WebSocketLike; sockets: MockWebSocket[] } {
  const sockets: MockWebSocket[] = [];
  const factory = (url: string): WebSocketLike => {
    const ws = new MockWebSocket(url);
    sockets.push(ws);
    return ws;
  };
  return { factory, sockets };
}
