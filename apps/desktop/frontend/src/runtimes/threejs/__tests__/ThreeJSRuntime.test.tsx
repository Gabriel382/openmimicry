/**
 * `<ThreeJSRuntime />` — mount + directive dispatch.
 *
 * The loader is injected so no real Three.js / VRM stack is touched.
 * The test asserts: a directive triggers `playClip` + `setExpression` +
 * `setGazeTarget` against the controller, and an unknown gesture is
 * dropped silently.
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

afterEach(() => cleanup());

describe("<ThreeJSRuntime />", () => {
  it("loads the asset and dispatches the initial directive", async () => {
    const controller = makeFakeController();
    const vrmLoader = vi.fn().mockResolvedValue(controller);
    render(<ThreeJSRuntime projection={projection()} vrmLoader={vrmLoader} />);

    await waitFor(() => expect(vrmLoader).toHaveBeenCalled());
    expect(vrmLoader).toHaveBeenCalledWith("/static/characters/test/character.vrm");
    await waitFor(() =>
      expect(controller.playClip).toHaveBeenCalledWith("idle", 220),
    );
    expect(controller.setGazeTarget).toHaveBeenCalledWith("towards_user");
  });

  it("dispatches a new clip when the projection changes", async () => {
    const controller = makeFakeController();
    const vrmLoader = vi.fn().mockResolvedValue(controller);
    const { rerender } = render(
      <ThreeJSRuntime projection={projection()} vrmLoader={vrmLoader} />,
    );
    await waitFor(() => expect(controller.playClip).toHaveBeenCalled());
    (controller.playClip as ReturnType<typeof vi.fn>).mockClear();

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
    await waitFor(() =>
      expect(controller.playClip).toHaveBeenCalledWith(
        "happy_speaking_speaking",
        220,
      ),
    );
    expect(controller.setExpression).toHaveBeenLastCalledWith(
      expect.objectContaining({ happy: 0.7 }),
    );
  });

  it("layers a gesture clip when one is named", async () => {
    const controller = makeFakeController();
    const vrmLoader = vi.fn().mockResolvedValue(controller);
    render(
      <ThreeJSRuntime
        projection={projection({
          directive: { state: "idle", emotion: "happy", gesture: "wave" },
          gestureClip: "wave",
        })}
        vrmLoader={vrmLoader}
      />,
    );
    await waitFor(() => expect(controller.playClip).toHaveBeenCalledWith("wave", 220));
  });

  it("falls back to a chain clip when the preferred name is missing", async () => {
    const controller = makeFakeController();
    const vrmLoader = vi.fn().mockResolvedValue(controller);
    render(
      <ThreeJSRuntime
        projection={projection({
          directive: { state: "speaking", emotion: "happy", speaking: true },
          clip: "happy_speaking_speaking",
          fallbackClips: ["happy_speaking_speaking", "speaking", "idle"],
        })}
        vrmLoader={vrmLoader}
      />,
    );
    // The fake controller's manifest includes "speaking" but the
    // preferred name "happy_speaking_speaking" is also there; the
    // component plays it as-is.
    await waitFor(() =>
      expect(controller.playClip).toHaveBeenCalledWith(
        "happy_speaking_speaking",
        220,
      ),
    );
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
    const { unmount } = render(
      <ThreeJSRuntime projection={projection()} vrmLoader={vrmLoader} />,
    );
    await waitFor(() => expect(controller.playClip).toHaveBeenCalled());
    unmount();
    expect(controller.dispose).toHaveBeenCalled();
  });
});
