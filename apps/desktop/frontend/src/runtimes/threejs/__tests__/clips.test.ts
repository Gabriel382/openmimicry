import { describe, expect, it } from "vitest";

import { clipFallbackChain, pickClip, pickGestureClip } from "../clips";

describe("clipFallbackChain", () => {
  it("idle neutral non-speaking → ['neutral_idle', 'idle']", () => {
    expect(clipFallbackChain("idle", "neutral", false)).toEqual([
      "neutral_idle",
      "idle",
    ]);
  });

  it("speaking happy puts the most-specific name first", () => {
    const chain = clipFallbackChain("speaking", "happy", true);
    expect(chain[0]).toBe("happy_speaking_speaking");
    expect(chain).toContain("happy_speaking");
    expect(chain).toContain("speaking");
    expect(chain[chain.length - 1]).toBe("idle");
  });

  it("dedupes entries while preserving order", () => {
    const chain = clipFallbackChain("idle", "neutral", true);
    expect(new Set(chain).size).toBe(chain.length);
  });
});

describe("pickClip", () => {
  it("picks the first available clip", () => {
    expect(
      pickClip({
        state: "speaking",
        emotion: "happy",
        speaking: true,
        available: ["happy_speaking", "speaking", "idle"],
      }),
    ).toBe("happy_speaking");
  });

  it("falls through to 'speaking' when 'happy_speaking' is missing", () => {
    expect(
      pickClip({
        state: "speaking",
        emotion: "happy",
        speaking: true,
        available: ["speaking", "idle"],
      }),
    ).toBe("speaking");
  });

  it("falls back to 'idle' when nothing in the chain matches", () => {
    expect(
      pickClip({
        state: "happy",
        emotion: "neutral",
        speaking: false,
        available: ["idle"],
      }),
    ).toBe("idle");
  });

  it("uses last chain entry when 'idle' is also missing", () => {
    expect(
      pickClip({
        state: "happy",
        emotion: "neutral",
        speaking: false,
        available: ["happy"],
      }),
    ).toBe("happy");
  });
});

describe("pickGestureClip", () => {
  it("returns the gesture when the manifest has it", () => {
    expect(pickGestureClip("wave", ["wave", "idle"])).toBe("wave");
  });

  it("matches a gesture_ prefix if present", () => {
    expect(pickGestureClip("wave", ["gesture_wave", "idle"])).toBe("gesture_wave");
  });

  it("returns null for unknown gestures", () => {
    expect(pickGestureClip("definitely-not", ["idle"])).toBeNull();
  });

  it("returns null for empty/undefined gesture", () => {
    expect(pickGestureClip(null, ["idle"])).toBeNull();
    expect(pickGestureClip(undefined, ["idle"])).toBeNull();
    expect(pickGestureClip("", ["idle"])).toBeNull();
  });
});
