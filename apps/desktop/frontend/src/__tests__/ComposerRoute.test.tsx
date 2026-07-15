import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ComposerRoute } from "../routes/ComposerRoute";
import { mockSocketFactory } from "../ws/mockSocket";
import { WSProvider } from "../ws/WSProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("avatar message composer", () => {
  it("renders below-avatar text input and sends user text", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline appearance"));
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <ComposerRoute />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets[0]?.readyState).toBe(1));

    const input = screen.getByLabelText("message");
    fireEvent.change(input, { target: { value: "hello Mimi" } });
    act(() => screen.getByLabelText("send").click());

    const sent = sockets[0]?.sent.map((message) => JSON.parse(message));
    expect(sent).toContainEqual({ type: "user.text", text: "hello Mimi" });
  });
});
