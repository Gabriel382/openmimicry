/**
 * Sprite2DRuntime — the React component that renders frame folders.
 *
 * Subscribes to `avatar.directive` messages with `runtime === "sprite2d"`
 * (delivered via the WS context provided by M7) and advances the current
 * frame index at the rate the projection specifies. `loop=false` clamps
 * at the last frame; `loop=true` wraps.
 *
 * This component is intentionally dumb. It does not derive state from
 * `RuntimeEvent`s -- the backend's `AvatarOrchestrator` has already done
 * that work, and the result arrives as a fully-resolved Sprite2D
 * projection.
 */

import { useEffect, useRef, useState } from "react";

import { preload } from "./preloader";

export type Sprite2DProjection = {
  type: "avatar.directive";
  runtime: "sprite2d";
  directive: {
    state: string;
    emotion?: string;
    speaking?: boolean;
    text?: string | null;
    [key: string]: unknown;
  };
  frames: string[];
  fps: number;
  loop: boolean;
};

export type Sprite2DRuntimeProps = {
  /** The current projection. Updated by the WS provider on every directive. */
  projection?: Sprite2DProjection;
  /** Optional className passed through to the wrapping element. */
  className?: string;
  /** Default fps applied before the first projection arrives. */
  defaultFps?: number;
};

const DEFAULT_FPS = 10;

export function Sprite2DRuntime(props: Sprite2DRuntimeProps) {
  const [currentIdx, setCurrentIdx] = useState<number>(0);
  const frames = props.projection?.frames ?? [];
  const fps = props.projection?.fps ?? props.defaultFps ?? DEFAULT_FPS;
  const loop = props.projection?.loop ?? true;
  const lastFramesRef = useRef<string[]>([]);

  // Preload + reset index whenever the frame set changes.
  useEffect(() => {
    if (frames === lastFramesRef.current) return;
    if (
      frames.length === lastFramesRef.current.length &&
      frames.every((f, i) => f === lastFramesRef.current[i])
    ) {
      return;
    }
    lastFramesRef.current = frames;
    setCurrentIdx(0);
    if (frames.length > 0) {
      // Fire-and-forget; the renderer is happy to show partially-loaded
      // frames since the cache is populated by the preloader.
      preload(frames).catch(() => {
        // already logged via the onError hook
      });
    }
  }, [frames]);

  // Advance the frame index at the configured rate.
  useEffect(() => {
    if (frames.length <= 1 || fps <= 0) {
      return;
    }
    const intervalMs = Math.max(1, Math.floor(1000 / fps));
    const handle = setInterval(() => {
      setCurrentIdx((idx) => {
        const next = idx + 1;
        if (next >= frames.length) {
          return loop ? 0 : frames.length - 1;
        }
        return next;
      });
    }, intervalMs);
    return () => clearInterval(handle);
  }, [frames, fps, loop]);

  if (frames.length === 0) {
    return (
      <div
        className={`avatar avatar--sprite2d avatar--empty ${props.className ?? ""}`}
        data-state="idle"
        data-frames="0"
      />
    );
  }

  const src = frames[Math.min(currentIdx, frames.length - 1)];
  return (
    <div
      className={`avatar avatar--sprite2d ${props.className ?? ""}`}
      data-state={props.projection?.directive?.state ?? "idle"}
      data-frames={String(frames.length)}
      data-frame-idx={String(currentIdx)}
    >
      <img
        className="avatar-frame"
        src={src}
        alt={String(props.projection?.directive?.state ?? "avatar")}
      />
    </div>
  );
}
