/**
 * Scene-config tests with a stubbed `three`. We don't render anything;
 * we just verify the helpers call into Three.js with sensible arguments.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

// --- Stub `three` ---------------------------------------------------------

class StubVector3 {
  constructor(public x = 0, public y = 0, public z = 0) {}
}

class StubObject3D {
  public position = { set: vi.fn() };
  public add = vi.fn();
}

class StubScene extends StubObject3D {}

class StubPerspectiveCamera extends StubObject3D {
  public aspect: number;
  public lookAt = vi.fn();
  public updateProjectionMatrix = vi.fn();
  constructor(public fov: number, aspect: number, public near: number, public far: number) {
    super();
    this.aspect = aspect;
  }
}

class StubDirectionalLight extends StubObject3D {
  constructor(public color: number, public intensity: number) {
    super();
  }
}
class StubHemisphereLight extends StubObject3D {
  constructor(public sky: number, public ground: number, public intensity: number) {
    super();
  }
}
class StubAmbientLight extends StubObject3D {
  constructor(public color: number, public intensity: number) {
    super();
  }
}
class StubPointLight extends StubObject3D {
  constructor(public color: number, public intensity: number) {
    super();
  }
}

const setSize = vi.fn();
const setPixelRatio = vi.fn();
const dispose = vi.fn();

class StubRenderer {
  setSize = setSize;
  setPixelRatio = setPixelRatio;
  dispose = dispose;
}

vi.mock("three", () => ({
  Vector3: StubVector3,
  Scene: StubScene,
  PerspectiveCamera: StubPerspectiveCamera,
  DirectionalLight: StubDirectionalLight,
  HemisphereLight: StubHemisphereLight,
  AmbientLight: StubAmbientLight,
  PointLight: StubPointLight,
  WebGLRenderer: StubRenderer,
}));

import { attachLighting, configureCamera, createScene } from "../scene";

beforeEach(() => {
  setSize.mockClear();
  setPixelRatio.mockClear();
  dispose.mockClear();
});

describe("configureCamera", () => {
  it("respects width/height aspect and config overrides", () => {
    const cam = configureCamera({ width: 800, height: 400 }) as unknown as StubPerspectiveCamera;
    expect(cam.aspect).toBeCloseTo(2);
    expect(cam.fov).toBe(30);
    expect(cam.lookAt).toHaveBeenCalled();
  });

  it("uses custom fov + position when provided", () => {
    const cam = configureCamera({
      width: 360,
      height: 360,
      camera: { fov: 50, position: [0, 1, 2] },
    }) as unknown as StubPerspectiveCamera;
    expect(cam.fov).toBe(50);
    expect(cam.position.set).toHaveBeenCalledWith(0, 1, 2);
  });
});

describe("attachLighting", () => {
  it("studio preset adds three lights", () => {
    const scene = new StubScene() as unknown as StubScene;
    attachLighting(scene as never, "studio");
    expect((scene.add as ReturnType<typeof vi.fn>).mock.calls.length).toBe(3);
  });

  it("outdoor preset adds sun + sky", () => {
    const scene = new StubScene() as unknown as StubScene;
    attachLighting(scene as never, "outdoor");
    expect((scene.add as ReturnType<typeof vi.fn>).mock.calls.length).toBe(2);
  });

  it("flat preset adds ambient + rim", () => {
    const scene = new StubScene() as unknown as StubScene;
    attachLighting(scene as never, "flat");
    expect((scene.add as ReturnType<typeof vi.fn>).mock.calls.length).toBe(2);
  });
});

describe("createScene", () => {
  it("builds scene + camera + renderer and exposes resize/dispose", () => {
    const handles = createScene({ width: 360, height: 360 });
    expect(setSize).toHaveBeenCalledWith(360, 360, false);
    expect(setPixelRatio).toHaveBeenCalled();

    handles.resize(800, 600);
    expect(setSize).toHaveBeenCalledWith(800, 600, false);

    handles.dispose();
    expect(dispose).toHaveBeenCalled();
  });

  it("accepts an injected renderer factory", () => {
    const fake = { setSize, setPixelRatio, dispose };
    const handles = createScene({
      width: 100,
      height: 100,
      rendererFactory: () => fake as unknown as InstanceType<typeof StubRenderer>,
    });
    expect(handles.renderer).toBe(fake);
  });
});
