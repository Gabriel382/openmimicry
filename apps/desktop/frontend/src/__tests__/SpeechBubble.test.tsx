/**
 * `<SpeechBubble />` — incremental text + configurable reading time.
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

  it("clears an incomplete prior reply when a new LLM turn starts", async () => {
    const { factory, sockets } = mockSocketFactory();
    const { container } = render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <SpeechBubble />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    const ws = sockets[0]!;

    act(() =>
      ws._dispatchMessage({ type: "bubble.text", text: "old unfinished", complete: false }),
    );
    await waitFor(() => expect(container.textContent).toContain("old unfinished"));

    act(() =>
      ws._dispatchMessage({
        type: "bubble.text",
        text: "",
        complete: false,
        reset: true,
      }),
    );
    expect(container.querySelector(".speech-bubble")).toBeNull();

    act(() =>
      ws._dispatchMessage({ type: "bubble.text", text: "new reply", complete: false }),
    );
    await waitFor(() => expect(container.textContent).toContain("new reply"));
    expect(container.textContent).not.toContain("old unfinished");
  });

  it("does not erase a completed reply merely because listening starts", async () => {
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
    expect(container.querySelector(".speech-bubble")?.textContent).toContain("stale");
  });

  it("clears after the configured reading-time formula", async () => {
    const { factory, sockets } = mockSocketFactory();
    const { container } = render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <SpeechBubble timing={{ base_ms: 10, ms_per_character: 0, max_ms: 20 }} />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    act(() =>
      sockets[0]!._dispatchMessage({ type: "bubble.text", text: "read me", complete: true }),
    );
    await waitFor(() => expect(container.querySelector(".speech-bubble")).not.toBeNull());
    await waitFor(() => expect(container.querySelector(".speech-bubble")).toBeNull());
  });
});
