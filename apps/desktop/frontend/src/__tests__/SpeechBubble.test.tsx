/**
 * `<SpeechBubble />` — incremental text + reset on listening.
 */

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { SpeechBubble } from "../components/SpeechBubble";
import { mockSocketFactory } from "../ws/mockSocket";
import { WSProvider } from "../ws/WSProvider";

afterEach(() => cleanup());

describe("<SpeechBubble />", () => {
  it("renders nothing when no bubble.text has been received", async () => {
    const { factory, sockets } = mockSocketFactory();
    const { container } = render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <SpeechBubble />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    expect(container.querySelector(".speech-bubble")).toBeNull();
  });

  it("accumulates partials and replaces on complete=true", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <SpeechBubble />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    const ws = sockets[0]!;

    act(() => ws._dispatchMessage({ type: "bubble.text", text: "Hel", complete: false }));
    act(() => ws._dispatchMessage({ type: "bubble.text", text: "lo", complete: false }));
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain("Hello"),
    );

    act(() =>
      ws._dispatchMessage({ type: "bubble.text", text: "Hello, world", complete: true }),
    );
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain("Hello, world"),
    );
  });

  it("clears on avatar.directive state=listening", async () => {
    const { factory, sockets } = mockSocketFactory();
    const { container } = render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <SpeechBubble />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    const ws = sockets[0]!;

    act(() =>
      ws._dispatchMessage({ type: "bubble.text", text: "stale", complete: true }),
    );
    await waitFor(() => expect(container.querySelector(".speech-bubble")).not.toBeNull());

    act(() =>
      ws._dispatchMessage({
        type: "avatar.directive",
        runtime: "sprite2d",
        directive: { state: "listening" },
      }),
    );
    await waitFor(() => expect(container.querySelector(".speech-bubble")).toBeNull());
  });
});
