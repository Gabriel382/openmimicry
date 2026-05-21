/**
 * `reconnect.ts` — backoff math + attempts bookkeeping.
 */

import { describe, expect, it } from "vitest";

import { createReconnectController } from "../ws/reconnect";

describe("createReconnectController", () => {
  it("starts at initialMs and doubles per attempt (no jitter)", async () => {
    const slept: number[] = [];
    const ctrl = createReconnectController({
      initialMs: 100,
      maxMs: 10_000,
      jitterRatio: 0,
      sleep: (ms) => {
        slept.push(ms);
        return Promise.resolve();
      },
    });
    await ctrl.wait();
    await ctrl.wait();
    await ctrl.wait();
    expect(slept).toEqual([100, 200, 400]);
    expect(ctrl.attempts).toBe(3);
  });

  it("caps at maxMs", async () => {
    const slept: number[] = [];
    const ctrl = createReconnectController({
      initialMs: 1_000,
      maxMs: 2_000,
      jitterRatio: 0,
      sleep: (ms) => {
        slept.push(ms);
        return Promise.resolve();
      },
    });
    for (let i = 0; i < 5; i += 1) await ctrl.wait();
    expect(slept).toEqual([1_000, 2_000, 2_000, 2_000, 2_000]);
  });

  it("applies symmetric jitter when configured", async () => {
    const slept: number[] = [];
    const ctrl = createReconnectController({
      initialMs: 1_000,
      maxMs: 10_000,
      jitterRatio: 0.5,
      random: () => 1, // upper bound of jitter range
      sleep: (ms) => {
        slept.push(ms);
        return Promise.resolve();
      },
    });
    await ctrl.wait();
    // base=1000, spread=500, offset = (1-0.5)*2*500 = +500 -> 1500
    expect(slept[0]).toBe(1500);
  });

  it("reset() clears attempts and returns to initial delay", async () => {
    const slept: number[] = [];
    const ctrl = createReconnectController({
      initialMs: 100,
      maxMs: 1_000,
      jitterRatio: 0,
      sleep: (ms) => {
        slept.push(ms);
        return Promise.resolve();
      },
    });
    await ctrl.wait();
    await ctrl.wait();
    ctrl.reset();
    await ctrl.wait();
    expect(slept).toEqual([100, 200, 100]);
  });

  it("respects maxAttempts and reports hasAttemptsLeft()", async () => {
    const slept: number[] = [];
    const ctrl = createReconnectController({
      initialMs: 10,
      maxMs: 100,
      jitterRatio: 0,
      maxAttempts: 2,
      sleep: (ms) => {
        slept.push(ms);
        return Promise.resolve();
      },
    });
    expect(ctrl.hasAttemptsLeft()).toBe(true);
    await ctrl.wait();
    await ctrl.wait();
    expect(ctrl.hasAttemptsLeft()).toBe(false);
    await ctrl.wait();
    expect(slept).toEqual([10, 20]);
  });
});
