import { Box3, Euler, Vector3, type Object3D } from "three";

export interface ModelTransform {
  position: [number, number, number];
  /** Euler rotation in degrees, in XYZ order. */
  rotation: [number, number, number];
  scale: number;
  autoFit: boolean;
  targetHeight: number;
  targetY: number;
}

export interface ModelBasis {
  position: Vector3;
  rotation: Euler;
  scale: Vector3;
}

export const DEFAULT_MODEL_TRANSFORM: ModelTransform = {
  position: [0, 0, 0],
  rotation: [0, 0, 0],
  scale: 1,
  autoFit: true,
  targetHeight: 0.72,
  targetY: 1.3,
};

export function captureModelBasis(root: Object3D): ModelBasis {
  return {
    position: root.position.clone(),
    rotation: root.rotation.clone(),
    scale: root.scale.clone(),
  };
}

/**
 * Apply one absolute transform from the load-time basis.
 *
 * Resetting to the captured basis first is important: directives may arrive
 * many times per turn, and applying offsets incrementally is what made the
 * model drift across messages in earlier builds.
 */
export function applyModelTransform(
  root: Object3D,
  basis: ModelBasis,
  values: Partial<ModelTransform> | undefined,
): void {
  const transform = { ...DEFAULT_MODEL_TRANSFORM, ...(values ?? {}) };
  root.position.copy(basis.position);
  root.rotation.copy(basis.rotation);
  root.scale.copy(basis.scale);

  root.rotation.x += degrees(transform.rotation[0]);
  root.rotation.y += degrees(transform.rotation[1]);
  root.rotation.z += degrees(transform.rotation[2]);
  root.scale.multiplyScalar(clamp(transform.scale, 0.05, 10));
  root.updateMatrixWorld(true);

  if (transform.autoFit) {
    const initial = new Box3().setFromObject(root);
    const size = initial.getSize(new Vector3());
    if (Number.isFinite(size.y) && size.y > 1e-6) {
      root.scale.multiplyScalar(
        clamp(transform.targetHeight, 0.1, 3) / size.y,
      );
      root.updateMatrixWorld(true);
      const fitted = new Box3().setFromObject(root);
      const center = fitted.getCenter(new Vector3());
      root.position.x -= center.x;
      root.position.y += clamp(transform.targetY, -3, 5) - center.y;
      root.position.z -= center.z;
    }
  }

  root.position.x += clamp(transform.position[0], -20, 20);
  root.position.y += clamp(transform.position[1], -20, 20);
  root.position.z += clamp(transform.position[2], -20, 20);
  root.updateMatrixWorld(true);
}

function degrees(value: number): number {
  return (clamp(value, -360, 360) * Math.PI) / 180;
}

function clamp(value: number, low: number, high: number): number {
  return Number.isFinite(value) ? Math.max(low, Math.min(high, value)) : low;
}
