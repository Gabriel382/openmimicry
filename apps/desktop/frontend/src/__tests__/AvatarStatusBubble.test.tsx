import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AvatarStatusBubble } from "../components/AvatarStatusBubble";
import { mockSocketFactory } from "../ws/mockSocket";
import { WSProvider } from "../ws/WSProvider";

afterEach(cleanup);

describe("avatar operational status bubble", () => {
  it("renders thinking as a non-error avatar bubble", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <AvatarStatusBubble />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets[0]?.readyState).toBe(1));
    const socket = sockets[0];
    if (!socket) throw new Error("mock socket was not created");

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

    expect(screen.getByRole("status").textContent).toBe("Thinking…");
    expect(screen.getByRole("status").className).toContain("avatar-status-bubble");
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
