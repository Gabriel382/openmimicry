import { afterEach, describe, expect, it, vi } from "vitest";

import {
  _resetCache,
  getCached,
  isCached,
  preload,
} from "../preloader";

/**
 * jsdom (Vitest's default DOM env) provides `Image`, but it does not fire
 * `onload` automatically when you set `.src`. We stub the prototype so the
 * loader resolves synchronously and the cache layer can be exercised
 * without a real network.
 */
class FakeImage {
  src = "";
  complete = false;
  onload: (() => void) | null = null;
  onerror: ((event: Event | string) => void) | null = null;
  constructor() {
    setTimeout(() => {
      this.complete = true;
      this.onload?.();
    }, 0);
  }
}

const originalImage = globalThis.Image;

beforeEach(() => {
  _resetCache();
  // @ts-expect-error -- we are deliberately swapping Image for the test.
  globalThis.Image = FakeImage;
});

afterEach(() => {
  // @ts-expect-error -- restore the real Image constructor between tests.
  globalThis.Image = originalImage;
});

describe("preloader", () => {
  it("caches every frame URL after preload resolves", async () => {
    expect(isCached("/a.png")).toBe(false);
    await preload(["/a.png", "/b.png"]);
    expect(isCached("/a.png")).toBe(true);
    expect(isCached("/b.png")).toBe(true);
    expect(getCached("/a.png")).toBeDefined();
  });

  it("does not re-fetch a URL that is already cached", async () => {
    await preload(["/a.png"]);
    const first = getCached("/a.png");
    await preload(["/a.png"]);
    const second = getCached("/a.png");
    // Same image object is returned -- it was reused, not recreated.
    expect(second).toBe(first);
  });

  it("calls the onError hook when an image fails", async () => {
    class FailingImage {
      src = "";
      complete = false;
      onload: (() => void) | null = null;
      onerror: ((event: Event | string) => void) | null = null;
      constructor() {
        setTimeout(() => {
          this.onerror?.(new Event("error"));
        }, 0);
      }
    }
    // @ts-expect-error -- swap to the failing constructor for this test.
    globalThis.Image = FailingImage;
    const onError = vi.fn();
    await preload(["/x.png"], { onError });
    expect(onError).toHaveBeenCalledWith("/x.png", expect.anything());
  });
});
