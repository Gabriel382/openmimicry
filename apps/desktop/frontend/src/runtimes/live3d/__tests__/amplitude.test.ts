/**
 * Amplitude-mouth driver — proves the RMS pipeline + one-pole LPF.
 */

import { describe, expect, it } from "vitest";

import { createAmplitudeDriver } from "../mouth/amplitude";

// jsdom doesn't ship a real Web Audio stack; we build the smallest
// possible analyser stub that the driver exercises end-to-end.
class StubAnalyser {
  public fftSize = 1024;
  public smoothingTimeConstant = 0;
  private samples: number[] = new Array(1024).fill(128);

  setRMS(rms: number): void {
    // Build a square wave around 128 whose RMS equals `rms` (after
    // re-centring + /128). The driver computes `(x - 128) / 128` so a
    // ±k waveform yields RMS = k/128. Pick `k = round(rms * 128)`.
    const amp = Math.round(rms * 128);
    for (let i = 0; i < this.samples.length; i += 1) {
      this.samples[i] = i % 2 === 0 ? 128 + amp : 128 - amp;
    }
  }
  getByteTimeDomainData(buf: Uint8Array): void {
    for (let i = 0; i < buf.length; i += 1) buf[i] = this.samples[i] ?? 128;
  }
  disconnect(): void {}
}

class StubAudioContext {
  public analyser = new StubAnalyser();
  createAnalyser(): StubAnalyser {
    return this.analyser;
  }
}

class StubSource {
  public connectedTo: unknown = null;
  connect(target: unknown): void {
    this.connectedTo = target;
  }
  disconnect(_target?: unknown): void {
    this.connectedTo = null;
  }
}

function driver(rmsAt: (t: number) => number, opts?: Partial<{ smoothingMs: number; gain: number; openCurve: number }>) {
  const ctx = new StubAudioContext();
  let t = 0;
  const drv = createAmplitudeDriver(ctx as unknown as AudioContext, {
    smoothingMs: opts?.smoothingMs ?? 50,
    gain: opts?.gain ?? 1,
    openCurve: opts?.openCurve ?? 1,
    now: () => t,
  });
  drv.connect(new StubSource() as unknown as AudioNode);
  return {
    ctx,
    drv,
    advance(deltaMs: number, rms?: number): void {
      t += deltaMs;
      if (rms !== undefined) ctx.analyser.setRMS(rms);
    },
  };
}

describe("createAmplitudeDriver", () => {
  it("returns 0 when no audio energy is present", () => {
    const { drv, advance } = driver(() => 0);
    advance(0, 0);
    expect(drv.tick()).toBe(0);
  });

  it("ramps up smoothly toward a sustained amplitude", () => {
    const { drv, advance } = driver(() => 0.5, { smoothingMs: 100 });
    advance(0, 0.5);
    drv.tick(); // initial tick (dt=0 alpha=0 — no movement)

    advance(50, 0.5);
    const first = drv.tick();
    advance(50, 0.5);
    const second = drv.tick();
    advance(500, 0.5);
    const fourth = drv.tick();

    expect(first).toBeGreaterThan(0);
    expect(second).toBeGreaterThan(first);
    expect(fourth).toBeGreaterThan(second);
    expect(fourth).toBeLessThanOrEqual(1);
  });

  it("clamps the shaped amplitude to [0, 1] even with high gain", () => {
    const { drv, advance } = driver(() => 1, { gain: 100, openCurve: 1, smoothingMs: 1 });
    advance(0, 1);
    drv.tick();
    advance(100, 1);
    const v = drv.tick();
    expect(v).toBeLessThanOrEqual(1);
    expect(v).toBeGreaterThan(0.9);
  });

  it("decays back to 0 when amplitude drops", () => {
    const { drv, advance } = driver(() => 0.5, { smoothingMs: 50 });
    advance(0, 0.5);
    drv.tick();
    advance(1000, 0.5);
    const peak = drv.tick();
    advance(0, 0);
    advance(2000, 0);
    const tail = drv.tick();
    expect(tail).toBeLessThan(peak);
  });

  it("dispose() makes subsequent ticks return the cached value", () => {
    const { drv, advance } = driver(() => 0.5);
    advance(0, 0.5);
    drv.tick();
    advance(100, 0.5);
    const before = drv.tick();
    drv.dispose();
    advance(1_000_000, 0.5);
    const after = drv.tick();
    expect(after).toBe(before);
  });
});
