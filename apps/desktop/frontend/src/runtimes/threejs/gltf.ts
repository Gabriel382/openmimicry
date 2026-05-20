/**
 * Generic glTF / GLB loader, exposing a duck-typed interface that
 * matches `vrm.ts`.
 *
 * The actual `GLTFLoader` import is dynamic so Vitest doesn't have to
 * resolve a real WebGL stack on import. The loader factory is
 * pluggable so unit tests inject a fake.
 */

import type { AnimationClip, Object3D } from "three";

import type { CharacterController, CharacterLoadOptions, ExpressionWeights } from "./types";

interface GLTFLoaderLike {
  loadAsync(url: string): Promise<{ scene: Object3D; animations: AnimationClip[] }>;
}

export type GLTFLoaderFactory = () => Promise<GLTFLoaderLike>;

async function defaultLoaderFactory(): Promise<GLTFLoaderLike> {
  const mod: any = await import("three/examples/jsm/loaders/GLTFLoader.js");
  return new mod.GLTFLoader();
}

/**
 * Load a glTF / GLB asset and return a duck-typed `CharacterController`.
 * Expression weights are no-ops by default (plain glTF has no VRM
 * expression manager); morph-target packs can override this surface in
 * their own loader.
 */
export async function loadGltfCharacter(
  opts: CharacterLoadOptions & { loaderFactory?: GLTFLoaderFactory },
): Promise<CharacterController> {
  const loader = await (opts.loaderFactory ?? defaultLoaderFactory)();
  const result = await loader.loadAsync(opts.url);
  const root = result.scene;
  const clips = new Map<string, AnimationClip>();
  for (const clip of result.animations) {
    clips.set(clip.name, clip);
  }
  if (opts.scene) {
    opts.scene.add(root);
  }

  let activeClip: string | null = null;

  return {
    kind: "gltf",
    root,
    clipNames: Array.from(clips.keys()),
    setExpression(_weights: ExpressionWeights): void {
      // plain glTF doesn't carry VRM expressions; morph-target packs
      // would override this via a sibling loader.
    },
    playClip(name: string, _fadeMs = 0): void {
      activeClip = clips.has(name) ? name : activeClip;
    },
    currentClip(): string | null {
      return activeClip;
    },
    setGazeTarget(_target: string): void {
      // gaze is renderer-specific; default impl is a no-op.
    },
    dispose(): void {
      if (opts.scene) opts.scene.remove(root);
    },
  };
}
