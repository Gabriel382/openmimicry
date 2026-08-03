import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ThinkingBubble } from "../components/ThinkingBubble";
import { mockSocketFactory } from "../ws/mockSocket";
import { WSProvider } from "../ws/WSProvider";

afterEach(() => cleanup());

describe("<ThinkingBubble />", () => {
  it("uses a white progress balloon until reply presentation begins", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <ThinkingBubble />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets[0]?.readyState).toBe(1));
    const socket = sockets[0]!;

    act(() =>
      socket._dispatchMessage({
        type: "turn.state",
        turn_id: "turn-1",
        sequence: 1,
        state: "thinking",
        source: "text",
        ts: new Date().toISOString(),
      }),
    );
    const balloon = await screen.findByRole("status");
    expect(balloon.className).toContain("thinking-bubble");
    expect(balloon.textContent).toContain("THINKING");

    act(() =>
      socket._dispatchMessage({
        type: "bubble.text",
        text: "The answer is ready.",
        complete: true,
      }),
    );
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  });

  it("disappears when a turn fails instead of remaining stuck", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <ThinkingBubble />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets[0]?.readyState).toBe(1));
    const socket = sockets[0]!;

    act(() =>
      socket._dispatchMessage({
        type: "turn.state",
        turn_id: "turn-2",
        sequence: 2,
        state: "thinking",
        source: "text",
        ts: new Date().toISOString(),
      }),
    );
    await screen.findByRole("status");

    act(() =>
      socket._dispatchMessage({
        type: "turn.state",
        turn_id: "turn-2",
        sequence: 2,
        state: "failed",
        source: "text",
        reason: "LLM response timed out",
        ts: new Date().toISOString(),
      }),
    );
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  });
});
