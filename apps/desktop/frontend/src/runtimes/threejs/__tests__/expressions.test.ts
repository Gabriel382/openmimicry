import { describe, expect, it } from "vitest";

import { mergeWeights, resolveExpression } from "../expressions";

describe("resolveExpression", () => {
  it("returns an empty table for neutral", () => {
    expect(resolveExpression("neutral", 1)).toEqual({});
  });

  it("scales happy by intensity", () => {
    expect(resolveExpression("happy", 0.5)).toEqual({ happy: 0.5 });
    expect(resolveExpression("happy", 1)).toEqual({ happy: 1 });
    expect(resolveExpression("happy", 0)).toEqual({ happy: 0 });
  });

  it("clamps intensity to the unit interval", () => {
    expect(resolveExpression("happy", -1).happy).toBe(0);
    expect(resolveExpression("happy", 5).happy).toBe(1);
  });

  it("handles unknown emotion as neutral", () => {
    expect(resolveExpression("nope" as unknown as "happy", 1)).toEqual({});
  });

  it("returns a fresh object each call", () => {
    const a = resolveExpression("happy", 1);
    a.happy = 0;
    const b = resolveExpression("happy", 1);
    expect(b.happy).toBe(1);
  });

  it("includes neutral overlay for sad/worried", () => {
    expect(resolveExpression("sad", 1).neutral).toBe(0.3);
    expect(resolveExpression("worried", 1).sad).toBe(0.6);
  });
});

describe("mergeWeights", () => {
  it("later table overrides earlier for the same key", () => {
    expect(mergeWeights({ happy: 0.2 }, { happy: 0.8 })).toEqual({ happy: 0.8 });
  });

  it("merges disjoint keys", () => {
    expect(mergeWeights({ happy: 0.5 }, { sad: 0.3 })).toEqual({ happy: 0.5, sad: 0.3 });
  });

  it("clamps merged values to [0,1]", () => {
    expect(mergeWeights({ happy: 2 })).toEqual({ happy: 1 });
    expect(mergeWeights({ sad: -1 })).toEqual({ sad: 0 });
  });
});
