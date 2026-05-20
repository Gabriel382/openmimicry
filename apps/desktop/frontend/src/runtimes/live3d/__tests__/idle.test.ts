/**
 * Idle driver — breathing wave + saccade scheduling + pause invariant.
 */

import { describe, expect, it } from "vitest";

import { createIdleDriver } from "../idle";

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

describe("createIdleDriver", () => {
  it("breathing wave is bounded by amplitude", () => {
    const clock = timed();
    const drv = createIdleDriver({
      breathingAmplitude: 0.05,
      breathingPeriodMs: 1000,
      saccadeMinMs: 1_000_000,
      saccadeMaxMs: 1_000_000,
      now: clock.now,
      random: () => 0.5,
    });
    for (let step = 0; step < 20; step += 1) {
      clock.advance(50);
      const sample = drv.tick();
      expect(Math.abs(sample.breathing)).toBeLessThanOrEqual(0.05 + 1e-9);
    }
  });

  it("never produces saccades while paused (gesture pin)", () => {
    const clock = timed();
    const drv = createIdleDriver({
      breathingAmplitude: 0,
      breathingPeriodMs: 1000,
      saccadeMinMs: 100,
      saccadeMaxMs: 200,
      now: clock.now,
      random: () => 0,
    });
    drv.pauseWhileGesture(true);
    clock.advance(10_000);
    const sample = drv.tick();
    expect(sample.gazeOffset).toEqual({ x: 0, y: 0 });
  });

  it("triggers a saccade after the configured interval and keeps it bounded", () => {
    const clock = timed();
    const drv = createIdleDriver({
      breathingAmplitude: 0,
      breathingPeriodMs: 1000,
      saccadeMinMs: 100,
      saccadeMaxMs: 100,
      now: clock.now,
      random: () => 0.9,
    });
    drv.tick();
    clock.advance(150);
    const sample = drv.tick();
    expect(sample.gazeOffset.x).not.toBe(0);
    expect(Math.abs(sample.gazeOffset.x)).toBeLessThanOrEqual(1);
    expect(Math.abs(sample.gazeOffset.y)).toBeLessThanOrEqual(1);
  });

  it("reset() clears any current gaze offset", () => {
    const clock = timed();
    const drv = createIdleDriver({
      breathingAmplitude: 0,
      breathingPeriodMs: 1000,
      saccadeMinMs: 100,
      saccadeMaxMs: 100,
      now: clock.now,
      random: () => 0.9,
    });
    drv.tick();
    clock.advance(200);
    drv.tick();
    drv.reset();
    expect(drv.tick().gazeOffset).toEqual({ x: 0, y: 0 });
  });
});
