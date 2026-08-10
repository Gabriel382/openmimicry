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
  Group,
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
    expressions?: Array<{ expressionName: string }>;
    getExpression?(name: string): unknown | null;
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
  const modelRoot: Object3D = vrm?.scene ?? result.scene;
  // Keep user positioning on a stable outer root.  Procedural motion is
  // applied to the model child from an immutable basis, so changing lifecycle
  // states can never accumulate position/rotation drift between messages.
  const root = new Group();
  root.add(modelRoot);
  const clips = new Map<string, AnimationClip>();
  for (const clip of result.animations) {
    clips.set(clip.name, clip);
  }
  if (opts.scene) {
    opts.scene.add(root);
  }

  let activeClip: string | null = null;
  let activeAction: AnimationAction | null = null;
  const mixer = new AnimationMixer(modelRoot);
  const clipNames = Array.from(clips.keys());
  const restPosition = modelRoot.position.clone();
  const restRotation = modelRoot.rotation.clone();
  let proceduralState = "idle";
  let proceduralTime = 0;

  const resetProceduralTransform = (): void => {
    modelRoot.position.copy(restPosition);
    modelRoot.rotation.copy(restRotation);
  };

  return {
    kind: "vrm",
    root,
    clipNames,
    setExpression(weights: ExpressionWeights): void {
      const manager = vrm?.expressionManager;
      if (!manager) return;
      manager.resetValues?.();
      for (const [name, value] of Object.entries(weights)) {
        // Custom expressions can be registered after the character finishes
        // loading, so resolve the live manager collection for every update.
        const expressionNames = new Map(
          (manager.expressions ?? []).map((item) => [
            item.expressionName.toLowerCase(),
            item.expressionName,
          ]),
        );
        const selected = expressionNames.get(name.toLowerCase()) ?? name;
        manager.setValue(selected, value);
      }
      manager.update();
    },
    playClip(name: string, fadeMs = 0): void {
      const clip = clips.get(name);
      proceduralState = name || "idle";
      if (!clip) {
        if (activeAction) {
          activeAction.fadeOut(Math.max(0, fadeMs) / 1000);
          activeAction = null;
          activeClip = null;
        }
        return;
      }
      resetProceduralTransform();
      if (name === activeClip) return;
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
      if (!activeAction) {
        proceduralTime += deltaSec;
        resetProceduralTransform();
        const state = proceduralState.toLowerCase();
        const speaking = state.includes("speak");
        const listening = state.includes("listen");
        const thinking = state.includes("think") || state.includes("ponder");
        const happy = state.includes("happy") || state.includes("celebr");
        const error = state.includes("error") || state.includes("sad");
        const pace = speaking ? 7.0 : happy ? 4.2 : thinking ? 1.8 : 1.25;
        const phase = proceduralTime * pace;
        const bob = Math.sin(phase) * (speaking ? 0.012 : happy ? 0.018 : 0.006);
        modelRoot.position.y = restPosition.y + bob;
        modelRoot.rotation.x =
          restRotation.x + (listening ? -0.045 : speaking ? Math.sin(phase * 0.7) * 0.025 : 0);
        modelRoot.rotation.y =
          restRotation.y + (thinking ? Math.sin(phase * 0.55) * 0.055 : 0);
        modelRoot.rotation.z =
          restRotation.z +
          (listening ? 0.055 : error ? -0.035 : happy ? Math.sin(phase) * 0.025 : 0);
      }
      vrm?.update(deltaSec);
    },
    dispose(): void {
      resetProceduralTransform();
      mixer.stopAllAction();
      mixer.uncacheRoot(modelRoot);
      if (opts.scene) opts.scene.remove(root);
    },
  };
}
