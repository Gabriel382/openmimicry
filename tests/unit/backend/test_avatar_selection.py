from openmimicry_backend.avatar_selection import runtime_for_pack_kind


def test_pack_kinds_have_one_canonical_runtime() -> None:
    assert runtime_for_pack_kind("sprite2d") == "sprite2d"
    assert runtime_for_pack_kind("vrm") == "threejs"
    assert runtime_for_pack_kind("gltf") == "threejs"
    assert runtime_for_pack_kind("threejs") == "threejs"
    assert runtime_for_pack_kind("unity") == "unity"
    assert runtime_for_pack_kind("external") == "external"
    assert runtime_for_pack_kind("advanced2d") is None
