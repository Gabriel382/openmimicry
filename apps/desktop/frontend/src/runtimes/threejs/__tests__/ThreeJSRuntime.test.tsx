/**
 * `<ThreeJSRuntime />` — mount + projection state.
 *
 * The loader is injected so no real Three.js / VRM stack is touched.
 * These tests assert that the runtime loads assets, exposes ready/error
 * state, reflects projection changes in DOM state, and disposes the
 * injected controller on unmount.
 */

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ThreeJSRuntime, type ThreeJSProjection } from "../ThreeJSRuntime";
import type { CharacterController } from "../types";

function makeFakeController(): CharacterController {
  return {
    kind: "vrm",
    root: {} as never,
    clipNames: ["idle", "speaking", "happy_speaking_speaking", "wave"],
    setExpression: vi.fn(),
    playClip: vi.fn(),
    currentClip: vi.fn().mockReturnValue(null),
    setGazeTarget: vi.fn(),
    dispose: vi.fn(),
  };
}

const projection = (
  overrides: Partial<ThreeJSProjection> = {},
): ThreeJSProjection => ({
  type: "avatar.directive",
  runtime: "threejs",
  directive: { state: "idle", emotion: "neutral", speaking: false },
  asset: { kind: "vrm", url: "/static/characters/test/character.vrm" },
  clip: "idle",
  fallbackClips: ["idle"],
  expressionWeights: {},
  intensity: 1,
  gazeTarget: "towards_user",
  fadeMs: 220,
  ...overrides,
});

function getHost(container: HTMLElement): HTMLElement {
  const host = container.querySelector(".avatar--threejs");

  if (!(host instanceof HTMLElement)) {
    throw new Error("ThreeJSRuntime host not found");
  }

  return host;
}

afterEach(() => {
  cleanup();
});

describe("<ThreeJSRuntime />", () => {
  it("loads the asset and reaches ready state", async () => {
    const controller = makeFakeController();
    const vrmLoader = vi.fn().mockResolvedValue(controller);

    const { container } = render(
      <ThreeJSRuntime projection={projection()} vrmLoader={vrmLoader} />,
    );

    await waitFor(() => expect(vrmLoader).toHaveBeenCalled());

    expect(vrmLoader).toHaveBeenCalledWith(
      "/static/characters/test/character.vrm",
    );

    const host = getHost(container);

    await waitFor(() => {
      expect(host.getAttribute("data-status")).toBe("ready");
    });

    expect(host.getAttribute("data-state")).toBe("idle");
  });

  it("reflects a new directive state when the projection changes", async () => {
    const controller = makeFakeController();
    const vrmLoader = vi.fn().mockResolvedValue(controller);

    const { container, rerender } = render(
      <ThreeJSRuntime projection={projection()} vrmLoader={vrmLoader} />,
    );

    const host = getHost(container);

    await waitFor(() => {
      expect(host.getAttribute("data-status")).toBe("ready");
    });

    expect(host.getAttribute("data-state")).toBe("idle");

    rerender(
      <ThreeJSRuntime
        projection={projection({
          directive: { state: "speaking", emotion: "happy", speaking: true },
          clip: "happy_speaking_speaking",
          fallbackClips: ["happy_speaking_speaking", "speaking", "idle"],
          intensity: 0.7,
          expressionWeights: { happy: 0.7 },
        })}
        vrmLoader={vrmLoader}
      />,
    );

    await waitFor(() => {
      expect(host.getAttribute("data-state")).toBe("speaking");
    });
  });

  it("keeps ready state when a gesture clip is named", async () => {
    const controller = makeFakeController();
    const vrmLoader = vi.fn().mockResolvedValue(controller);

    const { container } = render(
      <ThreeJSRuntime
        projection={projection({
          directive: { state: "idle", emotion: "happy", gesture: "wave" },
          gestureClip: "wave",
        })}
        vrmLoader={vrmLoader}
      />,
    );

    const host = getHost(container);

    await waitFor(() => {
      expect(host.getAttribute("data-status")).toBe("ready");
    });

    expect(host.getAttribute("data-state")).toBe("idle");
  });

  it("keeps ready state when fallback clips are provided", async () => {
    const controller = makeFakeController();
    const vrmLoader = vi.fn().mockResolvedValue(controller);

    const { container } = render(
      <ThreeJSRuntime
        projection={projection({
          directive: { state: "speaking", emotion: "happy", speaking: true },
          clip: "happy_speaking_speaking",
          fallbackClips: ["happy_speaking_speaking", "speaking", "idle"],
        })}
        vrmLoader={vrmLoader}
      />,
    );

    const host = getHost(container);

    await waitFor(() => {
      expect(host.getAttribute("data-status")).toBe("ready");
    });

    expect(host.getAttribute("data-state")).toBe("speaking");
  });

  it("renders an error label when the loader rejects", async () => {
    const vrmLoader = vi.fn().mockRejectedValue(new Error("404: not found"));

    render(<ThreeJSRuntime projection={projection()} vrmLoader={vrmLoader} />);

    const errorLabel = await screen.findByRole("alert");

    expect(errorLabel.textContent).toMatch(/404/);
  });

  it("disposes the controller on unmount", async () => {
    const controller = makeFakeController();
    const vrmLoader = vi.fn().mockResolvedValue(controller);

    const { container, unmount } = render(
      <ThreeJSRuntime projection={projection()} vrmLoader={vrmLoader} />,
    );

    const host = getHost(container);

    await waitFor(() => {
      expect(host.getAttribute("data-status")).toBe("ready");
    });

    unmount();

    expect(controller.dispose).toHaveBeenCalled();
  });
});