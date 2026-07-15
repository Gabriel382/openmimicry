import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ControlsRoute } from "../routes/ControlsRoute";
import { mockSocketFactory } from "../ws/mockSocket";
import { WSProvider } from "../ws/WSProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("avatar toolbar", () => {
  it("exposes lock, voice, settings, exit, and both microphone modes", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline appearance"));
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <ControlsRoute />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets[0]?.readyState).toBe(1));
    expect(screen.getByLabelText("Drag avatar")).toBeTruthy();
    expect(screen.getByLabelText("Lock avatar position")).toBeTruthy();
    expect(screen.getByLabelText("Hold to talk")).toBeTruthy();
    expect(screen.getByLabelText("Wake listen off")).toBeTruthy();
    expect(screen.getByLabelText("Agent voice on")).toBeTruthy();
    expect(screen.getByLabelText("Open settings and tasks")).toBeTruthy();
    expect(screen.getByLabelText("Exit OpenMimicry")).toBeTruthy();
    expect(screen.queryByLabelText("message")).toBeNull();
  });

  it("sends wake-listening and press-to-talk messages", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline appearance"));
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <ControlsRoute />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets[0]?.readyState).toBe(1));
    const socket = sockets[0];
    if (!socket) throw new Error("mock socket was not created");

    act(() => screen.getByLabelText("Wake listen off").click());
    const ptt = screen.getByLabelText("Hold to talk");
    fireEvent.pointerDown(ptt, { button: 0, pointerId: 1 });
    fireEvent.pointerUp(ptt, { button: 0, pointerId: 1 });

    const sent = socket.sent.map((message) => JSON.parse(message));
    expect(sent).toContainEqual({
      type: "mode.toggle",
      key: "live_wake",
      value: true,
    });
    expect(sent).toContainEqual({ type: "ptt.down" });
    expect(sent).toContainEqual({ type: "ptt.up" });
  });
});
