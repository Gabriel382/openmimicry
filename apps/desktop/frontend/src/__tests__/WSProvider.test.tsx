/**
 * `WSProvider` — connect, dispatch, send, reconnect.
 *
 * Uses `MockWebSocket` injected via `socketFactory`. The reconnect path is
 * exercised with a zero-jitter, tiny-delay controller so the test runs
 * deterministically without fake timers.
 */

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MockWebSocket, mockSocketFactory } from "../ws/mockSocket";
import { WSProvider, useWS } from "../ws/WSProvider";
import type { ClientMessage, ServerMessage } from "../ws/protocol";

function StatusProbe(): JSX.Element {
  const ws = useWS();
  return (
    <div>
      <span data-testid="status">{ws.status}</span>
      <span data-testid="last">{ws.lastMessage ? ws.lastMessage.type : "none"}</span>
      <button
        data-testid="send"
        onClick={() => ws.send({ type: "user.text", text: "hi" } satisfies ClientMessage)}
      >
        send
      </button>
    </div>
  );
}

afterEach(() => cleanup());

describe("WSProvider", () => {
  it("opens the socket and reports status=open", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <StatusProbe />
      </WSProvider>,
    );

    await waitFor(() => expect(sockets.length).toBe(1));
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("open"),
    );
  });

  it("dispatches parsed messages and exposes lastMessage", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <StatusProbe />
      </WSProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("open"),
    );
    const ws = sockets[0] as MockWebSocket;

    const msg: ServerMessage = {
      type: "bubble.text",
      text: "hello",
      complete: true,
    };
    act(() => ws._dispatchMessage(msg));

    await waitFor(() =>
      expect(screen.getByTestId("last").textContent).toBe("bubble.text"),
    );
  });

  it("send() serialises a ClientMessage to the socket", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <StatusProbe />
      </WSProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("open"),
    );
    const ws = sockets[0] as MockWebSocket;

    act(() => {
      screen.getByTestId("send").click();
    });
    expect(ws.sent.length).toBe(1);
    expect(JSON.parse(ws.sent[0] as string)).toEqual({ type: "user.text", text: "hi" });
  });

  it("auto-reconnects after a server close", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider
        url="ws://test/ws"
        socketFactory={factory}
        reconnect={{ initialMs: 0, maxMs: 0, jitterRatio: 0 }}
      >
        <StatusProbe />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("open"),
    );

    act(() => (sockets[0] as MockWebSocket)._serverClose());

    await waitFor(() => expect(sockets.length).toBeGreaterThanOrEqual(2));
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("open"),
    );
  });

  it("ignores malformed inbound JSON without crashing", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <StatusProbe />
      </WSProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("open"),
    );
    const ws = sockets[0] as MockWebSocket;

    act(() => ws._dispatchMessage("not-json"));
    act(() => ws._dispatchMessage({ no: "type" }));
    expect(screen.getByTestId("last").textContent).toBe("none");
  });
});
