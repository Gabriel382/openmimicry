/**
 * Frame pre-loader for the Sprite2D runtime.
 *
 * Resolves once every frame URL has fired its `<img>.onload`. Frames are
 * cached by URL so a second `preload([...])` with overlapping URLs only
 * fetches the new ones.
 *
 * This module deliberately has zero React / DOM-test surface beyond the
 * `Image` constructor; Vitest exercises it via jsdom which provides
 * `Image`. Tests can also stub `Image` directly.
 */

const _cache: Map<string, HTMLImageElement> = new Map();

export function isCached(url: string): boolean {
  return _cache.has(url);
}

export function getCached(url: string): HTMLImageElement | undefined {
  return _cache.get(url);
}

/** Test-only: wipe the cache. Not exported via index.ts. */
export function _resetCache(): void {
  _cache.clear();
}

/**
 * Load (and cache) every URL in `frames`. Resolves once they have all
 * loaded; individual failures are logged via the optional `onError`
 * callback and do not reject the whole promise (the renderer can still
 * display the remaining frames).
 */
export function preload(
  frames: ReadonlyArray<string>,
  options: { onError?: (url: string, event: Event | string) => void } = {},
): Promise<HTMLImageElement[]> {
  const tasks: Promise<HTMLImageElement>[] = frames.map((url) => {
    const cached = _cache.get(url);
    if (cached !== undefined && cached.complete) {
      return Promise.resolve(cached);
    }
    return new Promise<HTMLImageElement>((resolve) => {
      const img = new Image();
      _cache.set(url, img);
      img.onload = () => resolve(img);
      img.onerror = (event) => {
        options.onError?.(url, event as Event);
        // Resolve with the (broken) image; the renderer skips it.
        resolve(img);
      };
      img.src = url;
    });
  });
  return Promise.all(tasks);
}
