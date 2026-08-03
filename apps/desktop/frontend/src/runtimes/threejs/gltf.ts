/**
 * Generic glTF / GLB loader, exposing a duck-typed interface that
 * matches `vrm.ts`.
 *
 * The actual `GLTFLoader` import is dynamic so Vitest doesn't have to
 * resolve a real WebGL stack on import. The loader factory is
 * pluggable so unit tests inject a fake.
 */

import {
  AnimationMixer,
  type AnimationAction,
  type AnimationClip,
  type Object3D,
} from "three";

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
  let activeAction: AnimationAction | null = null;
  const mixer = new AnimationMixer(root);

  return {
    kind: "gltf",
    root,
    clipNames: Array.from(clips.keys()),
    setExpression(_weights: ExpressionWeights): void {
      // plain glTF doesn't carry VRM expressions; morph-target packs
      // would override this via a sibling loader.
    },
    playClip(name: string, fadeMs = 0): void {
      const clip = clips.get(name);
      if (!clip || name === activeClip) return;
      const next = mixer.clipAction(clip);
      next.reset().play();
      if (activeAction) next.crossFadeFrom(activeAction, fadeMs / 1000, true);
      activeAction = next;
      activeClip = name;
    },
    currentClip(): string | null {
      return activeClip;
    },
    setGazeTarget(_target: string): void {
      // gaze is renderer-specific; default impl is a no-op.
    },
    update(deltaSec: number): void {
      mixer.update(deltaSec);
    },
    dispose(): void {
      mixer.stopAllAction();
      mixer.uncacheRoot(root);
      if (opts.scene) opts.scene.remove(root);
    },
  };
}
