/**
 * Live3D expression blending — layers M9 base + server weights +
 * amplitude-mouth + viseme weights.
 */

import { describe, expect, it } from "vitest";

import { amplitudeMouth, blendExpression } from "../expressions";

describe("amplitudeMouth", () => {
  it("returns 0 weights at amp=0", () => {
    expect(amplitudeMouth(0)).toEqual({ aa: 0, oh: 0 });
  });

  it("clamps amplitude to [0, 1]", () => {
    expect(amplitudeMouth(-1)).toEqual({ aa: 0, oh: 0 });
    expect(amplitudeMouth(2).aa).toBe(1);
  });

  it("`oh` weight is ~40% of `aa`", () => {
    const w = amplitudeMouth(0.5);
    expect(w.oh).toBeCloseTo(w.aa! * 0.4, 5);
  });
});

describe("blendExpression", () => {
  it("merges base emotion + server weights + amplitude mouth", () => {
    const out = blendExpression({
      emotion: "happy",
      intensity: 0.8,
      serverWeights: { surprised: 0.3 },
      amplitudeMouth: 0.5,
    });
    expect(out.happy).toBeCloseTo(0.8);
    expect(out.surprised).toBe(0.3);
    expect(out.aa).toBe(0.5);
  });

  it("viseme weights win when they overlap with amplitude", () => {
    const out = blendExpression({
      emotion: "neutral",
      amplitudeMouth: 0.5,
      visemeWeights: { aa: 0.1 },
    });
    expect(out.aa).toBe(0.1);
  });

  it("neutral emotion + amplitude only produces mouth weights", () => {
    const out = blendExpression({ amplitudeMouth: 0.2 });
    expect(out.aa).toBe(0.2);
    expect(Object.prototype.hasOwnProperty.call(out, "happy")).toBe(false);
  });

  it("clamps every merged value to [0, 1]", () => {
    const out = blendExpression({
      emotion: "happy",
      intensity: 1,
      serverWeights: { happy: 5 },
    });
    expect(out.happy).toBe(1);
  });
});
