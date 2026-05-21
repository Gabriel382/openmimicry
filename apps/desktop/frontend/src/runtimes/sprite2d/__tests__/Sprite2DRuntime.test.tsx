import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Sprite2DRuntime, type Sprite2DProjection } from "../Sprite2DRuntime";
import { _resetCache } from "../preloader";

/** Image stub: resolves onload synchronously after a microtask. */
class FakeImage {
  src = "";
  complete = false;
  onload: (() => void) | null = null;
  onerror: ((event: Event | string) => void) | null = null;

  constructor() {
    queueMicrotask(() => {
      this.complete = true;
      this.onload?.();
    });
  }
}

const projection = (
  overrides: Partial<Sprite2DProjection> = {},
): Sprite2DProjection => ({
  type: "avatar.directive",
  runtime: "sprite2d",
  directive: { state: "idle", emotion: "neutral", speaking: false },
  frames: [
    "/static/characters/octomimic/idle/0.png",
    "/static/characters/octomimic/idle/1.png",
  ],
  fps: 10,
  loop: true,
  ...overrides,
});

const originalImage = globalThis.Image;

beforeEach(() => {
  _resetCache();
  globalThis.Image = FakeImage as unknown as typeof Image;
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  globalThis.Image = originalImage;
});

describe("Sprite2DRuntime", () => {
  it("renders the first frame on mount", () => {
    render(<Sprite2DRuntime projection={projection()} />);

    const img = screen.getByRole("img") as HTMLImageElement;

    expect(img.getAttribute("src")).toBe(
      "/static/characters/octomimic/idle/0.png",
    );
  });

  it("advances frames at the configured fps", () => {
    render(<Sprite2DRuntime projection={projection({ fps: 10 })} />);

    // 10 fps -> 100ms per frame.
    vi.advanceTimersByTime(110);

    const img = screen.getByRole("img") as HTMLImageElement;

    expect(img.getAttribute("src")).toBe(
      "/static/characters/octomimic/idle/1.png",
    );
  });

  it("wraps when loop is true", () => {
    render(
      <Sprite2DRuntime projection={projection({ fps: 10, loop: true })} />,
    );

    vi.advanceTimersByTime(110); // frame 1
    vi.advanceTimersByTime(110); // wraps back to frame 0

    const img = screen.getByRole("img") as HTMLImageElement;

    expect(img.getAttribute("src")).toBe(
      "/static/characters/octomimic/idle/0.png",
    );
  });

  it("clamps at the last frame when loop is false", () => {
    render(
      <Sprite2DRuntime projection={projection({ fps: 10, loop: false })} />,
    );

    vi.advanceTimersByTime(110); // frame 1
    vi.advanceTimersByTime(110); // would wrap, but loop=false clamps
    vi.advanceTimersByTime(110);

    const img = screen.getByRole("img") as HTMLImageElement;

    expect(img.getAttribute("src")).toBe(
      "/static/characters/octomimic/idle/1.png",
    );
  });

  it("resets to frame 0 when the frame set changes", () => {
    const { rerender } = render(
      <Sprite2DRuntime projection={projection({ fps: 10 })} />,
    );

    vi.advanceTimersByTime(110); // advance to frame 1

    rerender(
      <Sprite2DRuntime
        projection={projection({
          frames: [
            "/static/characters/octomimic/happy/0.png",
            "/static/characters/octomimic/happy/1.png",
          ],
          fps: 10,
        })}
      />,
    );

    const img = screen.getByRole("img") as HTMLImageElement;

    expect(img.getAttribute("src")).toBe(
      "/static/characters/octomimic/happy/0.png",
    );
  });

  it("renders an empty wrapper when no projection has arrived", () => {
    const { container } = render(<Sprite2DRuntime />);

    const wrapper = container.querySelector(".avatar--sprite2d");

    expect(wrapper?.classList.contains("avatar--empty")).toBe(true);
  });
});