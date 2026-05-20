/**
 * `<TaskCard />` — driven by `task.card`. Clicking cancel sends `task.cancel`.
 */

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TaskCard } from "../components/TaskCard";
import { MockWebSocket, mockSocketFactory } from "../ws/mockSocket";
import { WSProvider } from "../ws/WSProvider";

afterEach(() => cleanup());

describe("<TaskCard />", () => {
  it("shows the empty placeholder before any task.card arrives", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <TaskCard />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    expect(screen.getByText(/no tasks running/i)).toBeTruthy();
  });

  it("renders a row per task and updates it in place", async () => {
    const { factory, sockets } = mockSocketFactory();
    const { container } = render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <TaskCard />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    const ws = sockets[0] as MockWebSocket;

    act(() =>
      ws._dispatchMessage({
        type: "task.card",
        update: {
          handle: { id: "t1", runtime: "mock" },
          status: "running",
          note: "step 1",
          ts: "2026-01-01T00:00:00Z",
        },
      }),
    );
    await waitFor(() =>
      expect(container.querySelectorAll("[data-handle-id='t1']").length).toBe(1),
    );
    expect(screen.getByText(/step 1/)).toBeTruthy();

    act(() =>
      ws._dispatchMessage({
        type: "task.card",
        update: {
          handle: { id: "t1", runtime: "mock" },
          status: "succeeded",
          note: "done",
          ts: "2026-01-01T00:00:01Z",
        },
      }),
    );
    await waitFor(() =>
      expect(
        container.querySelector("[data-handle-id='t1']")?.getAttribute("data-status"),
      ).toBe("succeeded"),
    );
    // Cancel button hidden after terminal status.
    expect(screen.queryByRole("button", { name: /cancel t1/i })).toBeNull();
  });

  it("clicking cancel sends task.cancel with the right handle", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <TaskCard />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    const ws = sockets[0] as MockWebSocket;
    await waitFor(() => expect(ws.readyState).toBe(1));

    act(() =>
      ws._dispatchMessage({
        type: "task.card",
        update: {
          handle: { id: "t-cancel", runtime: "mock" },
          status: "running",
          note: "long task",
          ts: "2026-01-01T00:00:00Z",
        },
      }),
    );
    const btn = await screen.findByRole("button", { name: /cancel t-cancel/i });
    act(() => btn.click());

    expect(ws.sent.length).toBe(1);
    const parsed = JSON.parse(ws.sent[0] as string);
    expect(parsed).toEqual({
      type: "task.cancel",
      handle: { id: "t-cancel", runtime: "mock" },
    });
  });
});
