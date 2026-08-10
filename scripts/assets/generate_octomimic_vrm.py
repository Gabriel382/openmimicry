#!/usr/bin/env python3
"""Generate OpenMimicry's small, deterministic VRM 1.0 test character.

The asset is deliberately generated from project-owned geometry so the
repository can redistribute it without inheriting a third-party avatar's
license.  It contains no textures, network-fetched content, or randomness.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

COMPONENT_FLOAT = 5126
COMPONENT_UNSIGNED_SHORT = 5123
TARGET_ARRAY_BUFFER = 34962
TARGET_ELEMENT_ARRAY_BUFFER = 34963


def _flatten(rows: Iterable[Sequence[float]]) -> list[float]:
    return [value for row in rows for value in row]


def _quat_z(angle: float) -> list[float]:
    return [0.0, 0.0, math.sin(angle / 2.0), math.cos(angle / 2.0)]


def _sphere(segments: int = 24, rings: int = 16) -> tuple[list[float], list[float], list[int]]:
    positions: list[list[float]] = []
    normals: list[list[float]] = []
    indices: list[int] = []
    for ring in range(rings + 1):
        phi = math.pi * ring / rings
        sin_phi = math.sin(phi)
        cos_phi = math.cos(phi)
        for segment in range(segments + 1):
            theta = 2.0 * math.pi * segment / segments
            normal = [sin_phi * math.cos(theta), cos_phi, sin_phi * math.sin(theta)]
            positions.append([0.5 * component for component in normal])
            normals.append(normal)
    stride = segments + 1
    for ring in range(rings):
        for segment in range(segments):
            a = ring * stride + segment
            b = a + stride
            indices.extend([a, b, a + 1, b, b + 1, a + 1])
    return _flatten(positions), _flatten(normals), indices


def _cylinder(segments: int = 20) -> tuple[list[float], list[float], list[int]]:
    positions: list[list[float]] = []
    normals: list[list[float]] = []
    indices: list[int] = []
    for y in (-0.5, 0.5):
        for segment in range(segments):
            theta = 2.0 * math.pi * segment / segments
            normal = [math.cos(theta), 0.0, math.sin(theta)]
            positions.append([0.5 * normal[0], y, 0.5 * normal[2]])
            normals.append(normal)
    for segment in range(segments):
        nxt = (segment + 1) % segments
        bottom = segment
        top = segment + segments
        indices.extend([bottom, top, nxt, nxt, top, nxt + segments])
    for y, normal_y in ((-0.5, -1.0), (0.5, 1.0)):
        center = len(positions)
        positions.append([0.0, y, 0.0])
        normals.append([0.0, normal_y, 0.0])
        rim = len(positions)
        for segment in range(segments):
            theta = 2.0 * math.pi * segment / segments
            positions.append([0.5 * math.cos(theta), y, 0.5 * math.sin(theta)])
            normals.append([0.0, normal_y, 0.0])
        for segment in range(segments):
            nxt = (segment + 1) % segments
            if normal_y > 0:
                indices.extend([center, rim + segment, rim + nxt])
            else:
                indices.extend([center, rim + nxt, rim + segment])
    return _flatten(positions), _flatten(normals), indices


def _cube() -> tuple[list[float], list[float], list[int]]:
    positions: list[float] = []
    normals: list[float] = []
    indices: list[int] = []
    faces = (
        ((0.0, 0.0, 1.0), ((-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5))),
        (
            (0.0, 0.0, -1.0),
            ((0.5, -0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5)),
        ),
        ((1.0, 0.0, 0.0), ((0.5, -0.5, 0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5))),
        (
            (-1.0, 0.0, 0.0),
            ((-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5)),
        ),
        ((0.0, 1.0, 0.0), ((-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5))),
        (
            (0.0, -1.0, 0.0),
            ((-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5), (-0.5, -0.5, 0.5)),
        ),
    )
    for normal, corners in faces:
        start = len(positions) // 3
        positions.extend(_flatten(corners))
        normals.extend(list(normal) * 4)
        indices.extend([start, start + 1, start + 2, start, start + 2, start + 3])
    return positions, normals, indices


@dataclass
class BufferBuilder:
    data: bytearray = field(default_factory=bytearray)
    views: list[dict[str, int]] = field(default_factory=list)
    accessors: list[dict[str, object]] = field(default_factory=list)

    def _align(self) -> None:
        self.data.extend(b"\x00" * ((-len(self.data)) % 4))

    def add(
        self,
        values: Sequence[float] | Sequence[int],
        *,
        component_type: int,
        value_type: str,
        components: int,
        target: int | None = None,
        include_bounds: bool = False,
    ) -> int:
        self._align()
        offset = len(self.data)
        if component_type == COMPONENT_FLOAT:
            payload = struct.pack(f"<{len(values)}f", *values)
        elif component_type == COMPONENT_UNSIGNED_SHORT:
            payload = struct.pack(f"<{len(values)}H", *values)
        else:  # pragma: no cover - generator only supports its own two formats
            raise ValueError(f"unsupported component type: {component_type}")
        self.data.extend(payload)
        view: dict[str, int] = {
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": len(payload),
        }
        if target is not None:
            view["target"] = target
        view_index = len(self.views)
        self.views.append(view)
        accessor: dict[str, object] = {
            "bufferView": view_index,
            "componentType": component_type,
            "count": len(values) // components,
            "type": value_type,
        }
        if include_bounds and values:
            rows = [
                values[index : index + components] for index in range(0, len(values), components)
            ]
            accessor["min"] = [min(row[index] for row in rows) for index in range(components)]
            accessor["max"] = [max(row[index] for row in rows) for index in range(components)]
        accessor_index = len(self.accessors)
        self.accessors.append(accessor)
        return accessor_index


def _material(
    name: str, rgba: Sequence[float], *, metallic: float = 0.0, roughness: float = 0.72
) -> dict[str, object]:
    return {
        "name": name,
        "pbrMetallicRoughness": {
            "baseColorFactor": list(rgba),
            "metallicFactor": metallic,
            "roughnessFactor": roughness,
        },
        "doubleSided": False,
    }


def build_vrm() -> bytes:
    buffers = BufferBuilder()
    meshes: list[dict[str, object]] = []
    for name, geometry in (("Sphere", _sphere()), ("Cylinder", _cylinder()), ("Cube", _cube())):
        positions, normals, indices = geometry
        position_accessor = buffers.add(
            positions,
            component_type=COMPONENT_FLOAT,
            value_type="VEC3",
            components=3,
            target=TARGET_ARRAY_BUFFER,
            include_bounds=True,
        )
        normal_accessor = buffers.add(
            normals,
            component_type=COMPONENT_FLOAT,
            value_type="VEC3",
            components=3,
            target=TARGET_ARRAY_BUFFER,
        )
        index_accessor = buffers.add(
            indices,
            component_type=COMPONENT_UNSIGNED_SHORT,
            value_type="SCALAR",
            components=1,
            target=TARGET_ELEMENT_ARRAY_BUFFER,
            include_bounds=True,
        )
        meshes.append(
            {
                "name": name,
                "primitives": [
                    {
                        "attributes": {"POSITION": position_accessor, "NORMAL": normal_accessor},
                        "indices": index_accessor,
                        "material": 0,
                    }
                ],
            }
        )

    materials = [
        _material("Octomimic orange", (0.95, 0.42, 0.13, 1.0)),
        _material("Eye white", (1.0, 0.98, 0.91, 1.0), roughness=0.4),
        _material("Pupil", (0.16, 0.055, 0.025, 1.0), roughness=0.5),
        _material("Mouth", (0.55, 0.12, 0.035, 1.0), roughness=0.6),
        _material("Suction highlight", (1.0, 0.65, 0.28, 1.0), roughness=0.55),
    ]

    # Each primitive has its own material index. Geometry remains shared.
    def mesh_variant(base: int, material: int, name: str) -> int:
        mesh = json.loads(json.dumps(meshes[base]))
        mesh["name"] = name
        mesh["primitives"][0]["material"] = material
        meshes.append(mesh)
        return len(meshes) - 1

    body_mesh = mesh_variant(0, 0, "BodySphere")
    white_mesh = mesh_variant(0, 1, "EyeWhiteSphere")
    pupil_mesh = mesh_variant(0, 2, "PupilSphere")
    mouth_mesh = mesh_variant(2, 3, "MouthCube")
    tentacle_mesh = mesh_variant(1, 0, "TentacleCylinder")
    highlight_mesh = mesh_variant(0, 4, "HighlightSphere")

    nodes: list[dict[str, object]] = [
        {
            "name": "OctomimicPlacement",
            "translation": [0.0, 0.85, 0.0],
            "scale": [0.45, 0.45, 0.45],
            "children": [1],
        },
        {"name": "OctomimicRoot", "children": []},
    ]
    placement = 0
    root = 1

    def visual_node(
        name: str,
        mesh: int,
        translation: Sequence[float],
        scale: Sequence[float],
        rotation: Sequence[float] | None = None,
    ) -> int:
        node: dict[str, object] = {
            "name": name,
            "mesh": mesh,
            "translation": list(translation),
            "scale": list(scale),
        }
        if rotation is not None:
            node["rotation"] = list(rotation)
        nodes.append(node)
        index = len(nodes) - 1
        children = nodes[root]["children"]
        assert isinstance(children, list)
        children.append(index)
        return index

    visual_node("Body", body_mesh, (0.0, 1.26, 0.0), (1.1, 1.08, 0.58))
    visual_node("EyeWhite", white_mesh, (0.0, 1.34, 0.296), (0.38, 0.32, 0.085))
    pupil = visual_node("Pupil", pupil_mesh, (0.0, 1.34, 0.354), (0.13, 0.105, 0.045))
    mouth = visual_node("Mouth", mouth_mesh, (0.0, 1.00, 0.341), (0.23, 0.032, 0.035))
    visual_node("Highlight", highlight_mesh, (-0.28, 1.57, 0.30), (0.09, 0.07, 0.025))

    for index, x in enumerate((-0.42, -0.21, 0.0, 0.21, 0.42), start=1):
        visual_node(
            f"Tentacle{index}",
            tentacle_mesh,
            (x, 0.60 - 0.05 * abs(index - 3), 0.0),
            (0.13, 0.66 - 0.04 * abs(index - 3), 0.13),
            _quat_z((index - 3) * -0.035),
        )
    left_arm = visual_node(
        "LeftArmVisual", tentacle_mesh, (-0.58, 1.05, -0.01), (0.1, 0.42, 0.1), _quat_z(-0.65)
    )
    right_arm = visual_node(
        "RightArmVisual", tentacle_mesh, (0.58, 1.05, -0.01), (0.1, 0.42, 0.1), _quat_z(0.65)
    )

    # VRM requires a humanoid map. These project-owned helper bones are hidden
    # transform nodes; they do not constrain the mascot's non-human silhouette.
    human_bones: dict[str, dict[str, int]] = {}

    def bone(name: str, parent: int, translation: Sequence[float]) -> int:
        nodes.append({"name": f"Humanoid_{name}", "translation": list(translation), "children": []})
        index = len(nodes) - 1
        parent_children = nodes[parent].setdefault("children", [])
        assert isinstance(parent_children, list)
        parent_children.append(index)
        human_bones[name] = {"node": index}
        return index

    hips = bone("hips", root, (0.0, 0.72, -0.08))
    spine = bone("spine", hips, (0.0, 0.32, 0.0))
    bone("head", spine, (0.0, 0.52, 0.0))
    left_upper_leg = bone("leftUpperLeg", hips, (-0.18, -0.08, 0.0))
    left_lower_leg = bone("leftLowerLeg", left_upper_leg, (0.0, -0.28, 0.0))
    bone("leftFoot", left_lower_leg, (0.0, -0.26, 0.08))
    right_upper_leg = bone("rightUpperLeg", hips, (0.18, -0.08, 0.0))
    right_lower_leg = bone("rightLowerLeg", right_upper_leg, (0.0, -0.28, 0.0))
    bone("rightFoot", right_lower_leg, (0.0, -0.26, 0.08))
    left_upper_arm = bone("leftUpperArm", spine, (-0.30, 0.20, 0.0))
    left_lower_arm = bone("leftLowerArm", left_upper_arm, (-0.22, -0.02, 0.0))
    bone("leftHand", left_lower_arm, (-0.18, -0.02, 0.0))
    right_upper_arm = bone("rightUpperArm", spine, (0.30, 0.20, 0.0))
    right_lower_arm = bone("rightLowerArm", right_upper_arm, (0.22, -0.02, 0.0))
    bone("rightHand", right_lower_arm, (0.18, -0.02, 0.0))

    animations: list[dict[str, object]] = []

    def animation(
        name: str,
        tracks: Sequence[tuple[int, str, Sequence[Sequence[float]]]],
        times: Sequence[float] = (0.0, 0.55, 1.1),
    ) -> None:
        time_accessor = buffers.add(
            list(times),
            component_type=COMPONENT_FLOAT,
            value_type="SCALAR",
            components=1,
            include_bounds=True,
        )
        samplers: list[dict[str, object]] = []
        channels: list[dict[str, object]] = []
        for node, path, values in tracks:
            components = 4 if path == "rotation" else 3
            output_accessor = buffers.add(
                _flatten(values),
                component_type=COMPONENT_FLOAT,
                value_type="VEC4" if components == 4 else "VEC3",
                components=components,
            )
            sampler_index = len(samplers)
            samplers.append(
                {"input": time_accessor, "output": output_accessor, "interpolation": "LINEAR"}
            )
            channels.append({"sampler": sampler_index, "target": {"node": node, "path": path}})
        animations.append({"name": name, "samplers": samplers, "channels": channels})

    def timeline(duration: float, frames: int = 13) -> tuple[float, ...]:
        return tuple(duration * index / (frames - 1) for index in range(frames))

    def sampled(
        times: Sequence[float],
        value,
    ) -> tuple[Sequence[float], ...]:
        duration = times[-1] or 1.0
        return tuple(value(time / duration) for time in times)

    idle_times = timeline(1.6, 17)
    animation(
        "idle",
        [
            (
                root,
                "translation",
                sampled(
                    idle_times,
                    lambda phase: (0, 0.018 * (1 - math.cos(phase * 2 * math.pi)), 0),
                ),
            )
        ],
        idle_times,
    )
    listening_times = timeline(1.35, 15)
    animation(
        "listening",
        [
            (
                root,
                "rotation",
                sampled(
                    listening_times,
                    lambda phase: _quat_z(0.055 * math.sin(phase * 2 * math.pi)),
                ),
            ),
            (
                pupil,
                "translation",
                sampled(
                    listening_times,
                    lambda phase: (
                        0.045 * math.sin(phase * 2 * math.pi),
                        1.34,
                        0.354,
                    ),
                ),
            ),
        ],
        listening_times,
    )
    thinking_times = timeline(1.8, 19)
    animation(
        "thinking",
        [
            (
                root,
                "rotation",
                sampled(
                    thinking_times,
                    lambda phase: _quat_z(0.075 * math.sin(phase * 2 * math.pi)),
                ),
            ),
            (
                pupil,
                "translation",
                sampled(
                    thinking_times,
                    lambda phase: (
                        0.055 * math.sin(phase * 2 * math.pi),
                        1.37 + 0.02 * math.cos(phase * 2 * math.pi),
                        0.354,
                    ),
                ),
            ),
        ],
        thinking_times,
    )
    speaking_times = timeline(0.72, 17)
    animation(
        "speaking",
        [
            (
                mouth,
                "scale",
                sampled(
                    speaking_times,
                    lambda phase: (
                        0.23,
                        0.032 + 0.068 * abs(math.sin(phase * 6 * math.pi)),
                        0.035,
                    ),
                ),
            ),
            (
                root,
                "translation",
                sampled(
                    speaking_times,
                    lambda phase: (0, 0.012 * (1 - math.cos(phase * 4 * math.pi)), 0),
                ),
            ),
        ],
        speaking_times,
    )
    happy_times = timeline(0.9, 13)
    animation(
        "happy",
        [
            (
                root,
                "scale",
                sampled(
                    happy_times,
                    lambda phase: tuple([1 + 0.04 * math.sin(phase * math.pi) ** 2] * 3),
                ),
            ),
            (
                root,
                "translation",
                sampled(
                    happy_times,
                    lambda phase: (0, 0.08 * math.sin(phase * math.pi) ** 2, 0),
                ),
            ),
        ],
        happy_times,
    )
    error_times = timeline(0.56, 15)
    animation(
        "error",
        [
            (
                root,
                "translation",
                sampled(
                    error_times,
                    lambda phase: (0.045 * math.sin(phase * 6 * math.pi), 0, 0),
                ),
            )
        ],
        error_times,
    )
    celebrate_times = timeline(1.0, 17)
    celebrate_tracks = [
        (
            root,
            "translation",
            sampled(
                celebrate_times,
                lambda phase: (0, 0.14 * math.sin(phase * math.pi) ** 2, 0),
            ),
        ),
        (
            left_arm,
            "rotation",
            sampled(
                celebrate_times,
                lambda phase: _quat_z(-0.65 - 0.53 * math.sin(phase * math.pi) ** 2),
            ),
        ),
        (
            right_arm,
            "rotation",
            sampled(
                celebrate_times,
                lambda phase: _quat_z(0.65 + 0.53 * math.sin(phase * math.pi) ** 2),
            ),
        ),
    ]
    animation("celebrate", celebrate_tracks, celebrate_times)
    animation("gesture_celebrate", celebrate_tracks, celebrate_times)
    wave_times = timeline(1.0, 17)
    wave_track = [
        (
            right_arm,
            "rotation",
            sampled(
                wave_times,
                lambda phase: _quat_z(
                    0.65
                    + 0.6 * math.sin(phase * math.pi) ** 2
                    + 0.12 * math.sin(phase * 6 * math.pi)
                ),
            ),
        )
    ]
    animation(
        "wave",
        wave_track,
        wave_times,
    )
    animation(
        "gesture_wave",
        wave_track,
        wave_times,
    )

    expressions = {
        "preset": {
            "happy": {
                "materialColorBinds": [
                    {"material": 0, "type": "color", "targetValue": [1.0, 0.64, 0.24, 1.0]}
                ]
            },
            "sad": {
                "materialColorBinds": [
                    {"material": 0, "type": "color", "targetValue": [0.30, 0.48, 0.92, 1.0]}
                ]
            },
            "angry": {
                "materialColorBinds": [
                    {"material": 0, "type": "color", "targetValue": [0.94, 0.12, 0.07, 1.0]}
                ]
            },
            "surprised": {
                "materialColorBinds": [
                    {"material": 0, "type": "color", "targetValue": [1.0, 0.78, 0.22, 1.0]}
                ]
            },
            "neutral": {
                "materialColorBinds": [
                    {"material": 0, "type": "color", "targetValue": [0.95, 0.42, 0.13, 1.0]}
                ]
            },
        }
    }
    gltf: dict[str, object] = {
        "asset": {
            "version": "2.0",
            "generator": "OpenMimicry deterministic Octomimic VRM generator v1.9.2",
            "copyright": "CC0-1.0 OpenMimicry contributors",
        },
        "scene": 0,
        "scenes": [{"name": "OctomimicVRM", "nodes": [placement]}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "animations": animations,
        "buffers": [{"byteLength": len(buffers.data)}],
        "bufferViews": buffers.views,
        "accessors": buffers.accessors,
        "extensionsUsed": ["VRMC_vrm"],
        "extensions": {
            "VRMC_vrm": {
                "specVersion": "1.0",
                "meta": {
                    "name": "Octomimic 3D",
                    "version": "1.0.0",
                    "authors": ["OpenMimicry contributors"],
                    "copyrightInformation": "Dedicated to the public domain under CC0-1.0.",
                    "references": ["https://github.com/henryperes/openmimicry"],
                    "licenseUrl": "https://vrm.dev/licenses/1.0/",
                    "avatarPermission": "everyone",
                    "allowExcessivelyViolentUsage": True,
                    "allowExcessivelySexualUsage": True,
                    "commercialUsage": "corporation",
                    "allowPoliticalOrReligiousUsage": True,
                    "allowAntisocialOrHateUsage": True,
                    "creditNotation": "unnecessary",
                    "allowRedistribution": True,
                    "modification": "allowModificationRedistribution",
                    "otherLicenseUrl": "https://creativecommons.org/publicdomain/zero/1.0/",
                },
                "humanoid": {"humanBones": human_bones},
                "expressions": expressions,
            }
        },
        "extras": {
            "openmimicry": {
                "pack": "octomimic_vrm",
                "states": ["idle", "listening", "thinking", "speaking", "happy", "error"],
                "gestures": ["wave", "celebrate"],
                "source": "scripts/assets/generate_octomimic_vrm.py",
            }
        },
    }
    json_chunk = json.dumps(gltf, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    json_chunk += b" " * ((-len(json_chunk)) % 4)
    bin_chunk = bytes(buffers.data)
    bin_chunk += b"\x00" * ((-len(bin_chunk)) % 4)
    total_length = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    return b"".join(
        (
            struct.pack("<4sII", b"glTF", 2, total_length),
            struct.pack("<II", len(json_chunk), 0x4E4F534A),
            json_chunk,
            struct.pack("<II", len(bin_chunk), 0x004E4942),
            bin_chunk,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("characters/octomimic_vrm/octomimic.vrm"),
        help="destination .vrm path (default: %(default)s)",
    )
    args = parser.parse_args()
    payload = build_vrm()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(f"Wrote {args.output} ({len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
