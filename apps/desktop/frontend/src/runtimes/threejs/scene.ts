/**
 * Three.js scene + camera + lighting setup.
 *
 * The scene is intentionally minimal: a single perspective camera, a
 * configurable lighting preset, and a transparent background so the
 * Tauri overlay window stays click-through-friendly. Camera + light
 * positions come from `runtimeConfig`; sensible defaults match a 360px
 * square overlay framing a VRM bust.
 */

import {
  AmbientLight,
  DirectionalLight,
  HemisphereLight,
  PerspectiveCamera,
  PointLight,
  Scene,
  Vector3,
  WebGLRenderer,
  type Renderer,
} from "three";

export type LightingPreset = "studio" | "outdoor" | "flat";

export interface CameraConfig {
  position?: [number, number, number];
  target?: [number, number, number];
  fov?: number;
  near?: number;
  far?: number;
}

export interface SceneConfig {
  width: number;
  height: number;
  camera?: CameraConfig;
  lighting?: LightingPreset;
  /** Pluggable renderer factory (tests inject a stub). */
  rendererFactory?: () => Renderer;
}

export interface SceneHandles {
  scene: Scene;
  camera: PerspectiveCamera;
  renderer: Renderer;
  resize(width: number, height: number): void;
  dispose(): void;
}

const DEFAULT_CAMERA: Required<CameraConfig> = {
  position: [0, 1.4, 1.6],
  target: [0, 1.3, 0],
  fov: 30,
  near: 0.1,
  far: 30,
};

/**
 * Build a complete Three.js scene from the config. Returns handles
 * the runtime component owns; `dispose()` releases GPU resources.
 */
export function createScene(config: SceneConfig): SceneHandles {
  const scene = new Scene();
  const camera = configureCamera(config);
  const renderer =
    config.rendererFactory?.() ??
    new WebGLRenderer({ alpha: true, antialias: true, premultipliedAlpha: false });

  applyRendererSize(renderer, config.width, config.height);
  attachLighting(scene, config.lighting ?? "studio");

  return {
    scene,
    camera,
    renderer,
    resize(w, h) {
      camera.aspect = w / Math.max(1, h);
      camera.updateProjectionMatrix();
      applyRendererSize(renderer, w, h);
    },
    dispose() {
      const r = renderer as Renderer & { dispose?: () => void };
      r.dispose?.();
    },
  };
}

export function configureCamera(config: SceneConfig): PerspectiveCamera {
  const cfg = { ...DEFAULT_CAMERA, ...(config.camera ?? {}) };
  const camera = new PerspectiveCamera(
    cfg.fov,
    config.width / Math.max(1, config.height),
    cfg.near,
    cfg.far,
  );
  camera.position.set(...cfg.position);
  camera.lookAt(new Vector3(...cfg.target));
  return camera;
}

/** Attach lighting to `scene` per the named preset. Returns the scene. */
export function attachLighting(scene: Scene, preset: LightingPreset): Scene {
  switch (preset) {
    case "studio": {
      const key = new DirectionalLight(0xffffff, 1.2);
      key.position.set(2, 3, 2);
      const fill = new DirectionalLight(0xb3c7ff, 0.5);
      fill.position.set(-2, 2, 1);
      const ambient = new AmbientLight(0xffffff, 0.3);
      scene.add(key);
      scene.add(fill);
      scene.add(ambient);
      break;
    }
    case "outdoor": {
      const sun = new DirectionalLight(0xffffff, 1.4);
      sun.position.set(3, 5, 2);
      const sky = new HemisphereLight(0xb0d8ff, 0x404020, 0.6);
      scene.add(sun);
      scene.add(sky);
      break;
    }
    case "flat": {
      const ambient = new AmbientLight(0xffffff, 1.0);
      const rim = new PointLight(0xffffff, 0.4);
      rim.position.set(0, 2, -2);
      scene.add(ambient);
      scene.add(rim);
      break;
    }
    default: {
      const _exhaustive: never = preset;
      void _exhaustive;
    }
  }
  return scene;
}

function applyRendererSize(renderer: Renderer, width: number, height: number): void {
  const r = renderer as Renderer & {
    setSize?: (w: number, h: number, updateStyle?: boolean) => void;
    setPixelRatio?: (ratio: number) => void;
  };
  if (typeof window !== "undefined" && r.setPixelRatio) {
    r.setPixelRatio(window.devicePixelRatio ?? 1);
  }
  r.setSize?.(width, height, false);
}
