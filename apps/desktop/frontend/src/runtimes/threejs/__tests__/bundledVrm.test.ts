import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

import { VRMLoaderPlugin } from "@pixiv/three-vrm";
import { Box3, Vector3 } from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { describe, expect, it } from "vitest";

import { loadVrmCharacter } from "../vrm";

const ASSET_PATH = resolve(
  process.cwd(),
  "../../../characters/octomimic_vrm/octomimic.vrm",
);
const ASSET_URL = pathToFileURL(ASSET_PATH);

async function parseBundledVrm() {
  const bytes = await readFile(ASSET_PATH);
  const data = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(data).set(bytes);
  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));
  return loader.parseAsync(data, "");
}

describe("bundled Octomimic VRM", () => {
  it("loads through the production VRM plugin with all lifecycle clips", async () => {
    const gltf = await parseBundledVrm();
    const vrm = gltf.userData.vrm;
    const bounds = new Box3().setFromObject(gltf.scene);
    const size = bounds.getSize(new Vector3());
    const center = bounds.getCenter(new Vector3());
    let meshCount = 0;
    gltf.scene.traverse((node) => {
      if ("isMesh" in node && node.isMesh) meshCount += 1;
    });

    expect(vrm).toBeTruthy();
    expect(vrm.meta.name).toBe("Octomimic 3D");
    expect(vrm.humanoid).toBeTruthy();
    expect(vrm.expressionManager).toBeTruthy();
    expect(meshCount).toBeGreaterThanOrEqual(10);
    expect(size.x).toBeLessThan(0.7);
    expect(size.y).toBeLessThan(0.8);
    expect(center.y).toBeCloseTo(1.3, 1);
    expect(gltf.animations.map((clip) => clip.name)).toEqual(
      expect.arrayContaining([
        "idle",
        "listening",
        "thinking",
        "speaking",
        "happy",
        "error",
        "wave",
        "celebrate",
      ]),
    );
  });

  it("resets the previous VRM expression before applying the next one", async () => {
    const gltf = await parseBundledVrm();
    const manager = gltf.userData.vrm.expressionManager;
    const controller = await loadVrmCharacter({
      url: ASSET_URL.href,
      loaderFactory: async () => ({
        loadAsync: async () => gltf,
      }),
    });

    controller.setExpression({ happy: 1 });
    expect(manager.getValue("happy")).toBe(1);

    controller.setExpression({ sad: 1 });
    expect(manager.getValue("happy")).toBe(0);
    expect(manager.getValue("sad")).toBe(1);

    controller.dispose();
  });
});
