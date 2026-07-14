/**
 * `<AvatarHost />` — registry lookup + projection passthrough.
 *
 * Registers a `MockRuntime` against `setRuntime`, drives the WSProvider
 * with two `avatar.directive` messages naming different runtimes, and
 * asserts the right component renders each time. Also covers the
 * unknown-runtime fallback to `PlaceholderRuntime`.
 */

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { AvatarHost } from "../components/AvatarHost";
import { mockSocketFactory } from "../ws/mockSocket";
import { WSProvider } from "../ws/WSProvider";
import {
  PlaceholderRuntime,
  runtimeRegistry,
  setRuntime,
} from "../runtimes/registry";

function MockRuntime(props: { projection?: unknown }): JSX.Element {
  const state =
    (props.projection &&
      typeof props.projection === "object" &&
      "directive" in (props.projection as Record<string, unknown>) &&
      ((props.projection as { directive?: { state?: unknown } }).directive
        ?.state ?? "")) ||
    "";
  return (
    <div data-testid="mock-runtime" data-state={String(state)}>
      MOCK
    </div>
  );
}

const originalSprite2D = runtimeRegistry["sprite2d"];

afterEach(() => {
  cleanup();
  // Restore the registry between tests.
  if (originalSprite2D) {
    setRuntime("sprite2d", originalSprite2D);
  }
  delete runtimeRegistry["mockruntime"];
});

beforeEach(() => {
  setRuntime("mockruntime", MockRuntime);
});

describe("<AvatarHost />", () => {
  it("renders the registered runtime when a directive names it", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <AvatarHost />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    const ws = sockets[0]!;
    act(() =>
      ws._dispatchMessage({
        type: "avatar.directive",
        runtime: "mockruntime",
        directive: { state: "thinking" },
      }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("mock-runtime").getAttribute("data-state")).toBe(
        "thinking",
      ),
    );
  });

  it("falls back to the placeholder for unknown runtimes", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <AvatarHost />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    const ws = sockets[0]!;
    act(() =>
      ws._dispatchMessage({
        type: "avatar.directive",
        runtime: "definitely-not-a-runtime",
        directive: { state: "happy" },
      }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("status", { name: /placeholder avatar runtime/i }),
      ).toBeTruthy(),
    );
  });

  it("uses defaultRuntime when no directive has been received", async () => {
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <AvatarHost defaultRuntime="mockruntime" />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    await waitFor(() =>
      expect(screen.getByTestId("mock-runtime").textContent).toBe("MOCK"),
    );
  });

  it("swaps between two runtimes when subsequent directives arrive", async () => {
    setRuntime("anotherruntime", () => <div data-testid="another">AN</div>);
    const { factory, sockets } = mockSocketFactory();
    render(
      <WSProvider url="ws://test/ws" socketFactory={factory}>
        <AvatarHost />
      </WSProvider>,
    );
    await waitFor(() => expect(sockets.length).toBe(1));
    const ws = sockets[0]!;
    act(() =>
      ws._dispatchMessage({
        type: "avatar.directive",
        runtime: "mockruntime",
        directive: { state: "idle" },
      }),
    );
    await waitFor(() => expect(screen.queryByTestId("mock-runtime")).toBeTruthy());

    act(() =>
      ws._dispatchMessage({
        type: "avatar.directive",
        runtime: "anotherruntime",
        directive: { state: "speaking" },
      }),
    );
    await waitFor(() => expect(screen.queryByTestId("another")).toBeTruthy());
    delete runtimeRegistry["anotherruntime"];
  });

  it("PlaceholderRuntime exposes the right state label", () => {
    render(<PlaceholderRuntime projection={{ directive: { state: "error" } }} />);
    expect(screen.getByRole("status").textContent).toMatch(/state=error/);
  });
});
