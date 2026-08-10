import { BoxGeometry, Mesh, Object3D } from "three";
import { describe, expect, it } from "vitest";

import { applyModelTransform, captureModelBasis } from "../transform";

describe("3D model transform", () => {
  it("defaults every unsaved model to a front-facing 180 degree Y rotation", () => {
    const root = new Object3D();
    root.add(new Mesh(new BoxGeometry(1, 2, 1)));

    applyModelTransform(root, captureModelBasis(root), undefined);

    expect(root.rotation.y).toBeCloseTo(Math.PI);
  });

  it("is absolute and does not drift when applied repeatedly", () => {
    const root = new Object3D();
    root.add(new Mesh(new BoxGeometry(1, 2, 1)));
    const basis = captureModelBasis(root);
    const transform = {
      position: [0.2, -0.1, 0.3] as [number, number, number],
      rotation: [0, 15, 0] as [number, number, number],
      scale: 1.2,
      autoFit: true,
      targetHeight: 0.72,
      targetY: 1.3,
    };

    applyModelTransform(root, basis, transform);
    const first = {
      position: root.position.toArray(),
      rotation: root.rotation.toArray(),
      scale: root.scale.toArray(),
    };
    applyModelTransform(root, basis, transform);

    expect(root.position.toArray()).toEqual(first.position);
    expect(root.rotation.toArray()).toEqual(first.rotation);
    expect(root.scale.toArray()).toEqual(first.scale);
  });
});
