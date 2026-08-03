/**
 * VRM loader. Uses `@pixiv/three-vrm` if available; the import is
 * dynamic so Vitest doesn't have to resolve the package at module-load
 * time.
 *
 * Returns a `CharacterController` whose `setExpression` actually drives
 * VRM expression weights — the only real difference from the
 * generic glTF loader.
 */

import {
  AnimationMixer,
  type AnimationAction,
  type AnimationClip,
  type Object3D,
} from "three";

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
    resetValues?(): void;
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
  const animationMod: any = await import("@pixiv/three-vrm-animation");
  const loader = new gltfMod.GLTFLoader();
  loader.register((parser: unknown) => new vrmMod.VRMLoaderPlugin(parser));
  loader.register(
    (parser: unknown) => new animationMod.VRMAnimationLoaderPlugin(parser),
  );
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
  let activeAction: AnimationAction | null = null;
  const mixer = new AnimationMixer(root);
  const clipNames = Array.from(clips.keys());

  return {
    kind: "vrm",
    root,
    clipNames,
    setExpression(weights: ExpressionWeights): void {
      const manager = vrm?.expressionManager;
      if (!manager) return;
      manager.resetValues?.();
      for (const [name, value] of Object.entries(weights)) {
        manager.setValue(name, value);
      }
      manager.update();
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
      // Gaze targets are a `THREE.Object3D`; for now we just expose the
      // hook. A future M9 follow-up wires it to a HEAD_FOLLOW dummy.
    },
    async loadAnimation(url: string, name?: string): Promise<void> {
      if (!vrm) return;
      const animationMod: any = await import("@pixiv/three-vrm-animation");
      const animationResult: any = await loader.loadAsync(url);
      const source = animationResult.userData?.vrmAnimations?.[0];
      if (!source) throw new Error(`VRMA contains no animation: ${url}`);
      const clip: AnimationClip = animationMod.createVRMAnimationClip(source, vrm);
      const selected = name || clip.name || `animation-${clips.size + 1}`;
      clip.name = selected;
      clips.set(selected, clip);
      if (!clipNames.includes(selected)) clipNames.push(selected);
    },
    update(deltaSec: number): void {
      mixer.update(deltaSec);
      vrm?.update(deltaSec);
    },
    dispose(): void {
      mixer.stopAllAction();
      mixer.uncacheRoot(root);
      if (opts.scene) opts.scene.remove(root);
    },
  };
}
