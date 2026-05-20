/**
 * Gaze driver — interpolation, no-snap, pack overrides.
 */

import { describe, expect, it } from "vitest";

import { createGazeDriver } from "../gaze";

function timed() {
  let t = 0;
  return {
    now(): number {
      return t;
    },
    advance(deltaMs: number): void {
      t += deltaMs;
    },
  };
}

describe("createGazeDriver", () => {
  it("interpolates between targets over blendWindowMs (no snapping)", () => {
    const clock = timed();
    const drv = createGazeDriver({ blendWindowMs: 100, now: clock.now });
    drv.snap("towards_user");
    const start = drv.current();
    expect(start.z).toBe(1);

    drv.setTarget("away");
    clock.advance(50);
    const halfway = drv.tick();
    expect(halfway.z).toBeGreaterThan(-1);
    expect(halfway.z).toBeLessThan(1);
  });

  it("converges to the target after blendWindowMs", () => {
    const clock = timed();
    const drv = createGazeDriver({ blendWindowMs: 100, now: clock.now });
    drv.snap("towards_user");
    drv.setTarget("down");
    clock.advance(150);
    const v = drv.tick();
    expect(v.y).toBeCloseTo(-1, 1);
  });

  it("snap() jumps without interpolation", () => {
    const clock = timed();
    const drv = createGazeDriver({ blendWindowMs: 1_000, now: clock.now });
    drv.snap("away");
    const v = drv.current();
    expect(v.z).toBe(-1);
  });

  it("supports pack-supplied target overrides", () => {
    const clock = timed();
    const drv = createGazeDriver({
      blendWindowMs: 50,
      now: clock.now,
      map: { custom: { x: 0.42, y: 0.42, z: 0.42 } },
    });
    drv.snap("custom");
    expect(drv.current()).toEqual({ x: 0.42, y: 0.42, z: 0.42 });
  });

  it("an unknown target leaves current value in place", () => {
    const clock = timed();
    const drv = createGazeDriver({ blendWindowMs: 50, now: clock.now });
    drv.snap("towards_user");
    drv.setTarget("not-a-gaze");
    clock.advance(100);
    expect(drv.tick().z).toBe(1);
  });

  it("a new target cancels the in-flight blend toward the old one", () => {
    const clock = timed();
    const drv = createGazeDriver({ blendWindowMs: 100, now: clock.now });
    drv.snap("towards_user");
    drv.setTarget("away");
    clock.advance(40);
    drv.tick();
    drv.setTarget("down");
    clock.advance(120);
    const final = drv.tick();
    expect(final.y).toBeCloseTo(-1, 1);
  });
});
