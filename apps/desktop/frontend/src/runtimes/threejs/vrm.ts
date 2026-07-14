/**
 * VRM loader. Uses `@pixiv/three-vrm` if available; the import is
 * dynamic so Vitest doesn't have to resolve the package at module-load
 * time.
 *
 * Returns a `CharacterController` whose `setExpression` actually drives
 * VRM expression weights — the only real difference from the
 * generic glTF loader.
 */

import type { AnimationClip, Object3D } from "three";

import type { CharacterController, CharacterLoadOptions, ExpressionWeights } from "./types";

interface VRMLoaderLike {
  loadAsync(url: string): Promise<{
    scene: Object3D;
    animations: AnimationClip[];
    userData?: { vrm?: VRMHandle };
  }>;
}

interface VRMHandle {
  scene: Object3D;
  expressionManager?: {
    setValue(name: string, value: number): void;
    update(): void;
  };
  lookAt?: { target?: Object3D };
  update(deltaSec: number): void;
}

export type VRMLoaderFactory = () => Promise<VRMLoaderLike>;

async function defaultLoaderFactory(): Promise<VRMLoaderLike> {
  const gltfMod: any = await import("three/examples/jsm/loaders/GLTFLoader.js");
  const vrmMod: any = await import("@pixiv/three-vrm");
  const loader = new gltfMod.GLTFLoader();
  loader.register((parser: unknown) => new vrmMod.VRMLoaderPlugin(parser));
  return loader;
}

export async function loadVrmCharacter(
  opts: CharacterLoadOptions & { loaderFactory?: VRMLoaderFactory },
): Promise<CharacterController> {
  const loader = await (opts.loaderFactory ?? defaultLoaderFactory)();
  const result = await loader.loadAsync(opts.url);
  const vrm = result.userData?.vrm;
  const root: Object3D = vrm?.scene ?? result.scene;
  const clips = new Map<string, AnimationClip>();
  for (const clip of result.animations) {
    clips.set(clip.name, clip);
  }
  if (opts.scene) {
    opts.scene.add(root);
  }

  let activeClip: string | null = null;

  return {
    kind: "vrm",
    root,
    clipNames: Array.from(clips.keys()),
    setExpression(weights: ExpressionWeights): void {
      const manager = vrm?.expressionManager;
      if (!manager) return;
      for (const [name, value] of Object.entries(weights)) {
        manager.setValue(name, value);
      }
      manager.update();
    },
    playClip(name: string, _fadeMs = 0): void {
      activeClip = clips.has(name) ? name : activeClip;
    },
    currentClip(): string | null {
      return activeClip;
    },
    setGazeTarget(_target: string): void {
      // Gaze targets are a `THREE.Object3D`; for now we just expose the
      // hook. A future M9 follow-up wires it to a HEAD_FOLLOW dummy.
    },
    dispose(): void {
      if (opts.scene) opts.scene.remove(root);
    },
  };
}
