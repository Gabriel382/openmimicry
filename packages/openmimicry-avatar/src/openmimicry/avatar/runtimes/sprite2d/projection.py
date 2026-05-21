"""``build_sprite2d_projection`` — turns an ``AvatarDirective`` into a wire-message.

The output shape (per ``docs/contracts.md`` §9 and M4 brief)::

    {
        "type": "avatar.directive",
        "runtime": "sprite2d",
        "directive": { /* AvatarDirective fields */ },
        "frames": ["frames/idle/0.png", ...],   # URL-relative paths
        "fps": 10,
        "loop": true,
    }

Rules (from ``docs/character_packs.md`` §4–§6):

* If ``directive.state`` exists in ``pack.emotions``, use that entry.
* Otherwise fall back to ``pack.default_state`` (the loader guarantees it
  exists). A one-shot warning is emitted by the adapter — the projection
  builder is pure.
* If ``directive.speaking`` is True AND the entry has ``speaking_frames``,
  use those. Otherwise fall back to ``frames`` (the loader has already
  resolved both to lists of paths, but the rule is preserved here for
  packs constructed directly from the schema without the loader).
* ``fps`` and ``loop`` come from the chosen :class:`EmotionFrames` entry.
"""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import Any

from openmimicry.core.schemas import AvatarDirective, CharacterPack, EmotionFrames

__all__ = ["build_sprite2d_projection", "frames_for_directive"]


def build_sprite2d_projection(
    directive: AvatarDirective,
    pack: CharacterPack,
    *,
    static_url_prefix: str = "/static/characters",
) -> dict[str, Any]:
    """Return the wire message for ``directive`` against ``pack``.

    Frame paths are rebased to URLs the frontend can fetch:
    ``{static_url_prefix}/{pack.id}/<relative path>``. The relative path is
    computed against the pack root by detecting the ``pack.id`` segment in
    the resolved path; if the pack was constructed without the loader and
    paths are not absolute, they are passed through unchanged.
    """
    entry = pack.emotions.get(directive.state)
    if entry is None:
        # Director / consumer normally guarantees this; the adapter logs the
        # warning. Here we just fall back so the message is always valid.
        entry = pack.emotions.get(pack.default_state)
        if entry is None and pack.emotions:
            entry = next(iter(pack.emotions.values()))

    if entry is None:
        # Pack has zero emotions; build a minimal projection so the frontend
        # can at least apply the directive metadata (state, emotion, text).
        return {
            "type": "avatar.directive",
            "runtime": "sprite2d",
            "directive": directive.model_dump(mode="json"),
            "frames": [],
            "fps": 10,
            "loop": True,
        }

    frame_paths = _select_frame_paths(entry, speaking=directive.speaking)
    url_frames = [_to_static_url(p, pack.id, static_url_prefix) for p in frame_paths]

    return {
        "type": "avatar.directive",
        "runtime": "sprite2d",
        "directive": directive.model_dump(mode="json"),
        "frames": url_frames,
        "fps": entry.fps,
        "loop": entry.loop,
    }


def frames_for_directive(
    directive: AvatarDirective, pack: CharacterPack
) -> list[str]:
    """Helper: return just the frame list (filesystem paths) for ``directive``.

    Useful for tests; the adapter's hot path goes through
    :func:`build_sprite2d_projection`.
    """
    entry = pack.emotions.get(directive.state) or pack.emotions.get(pack.default_state)
    if entry is None:
        return []
    return list(_select_frame_paths(entry, speaking=directive.speaking))


def _select_frame_paths(entry: EmotionFrames, *, speaking: bool) -> list[str]:
    """Pick speaking_frames vs base frames per the §6 fallback rule."""
    if speaking and entry.speaking_frames is not None:
        speaking_paths = _coerce_to_list(entry.speaking_frames)
        if speaking_paths:
            return speaking_paths
    return _coerce_to_list(entry.frames)


def _coerce_to_list(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return list(value)
    # Unresolved folder path. The loader normally turns this into a list,
    # but callers that hand us a raw schema get a one-element list back.
    return [value] if value else []


def _to_static_url(path: str, pack_id: str, prefix: str) -> str:
    """Rebase an absolute filesystem path onto the static URL prefix.

    Heuristic: find the ``pack_id`` segment in the path and take everything
    after it; prepend ``{prefix}/{pack_id}/``. Non-matching paths are
    returned unchanged so a pack built straight from a schema (with
    URL-shaped values) still works.
    """
    p = PurePath(path)
    if pack_id not in p.parts:
        return path
    # Slice to the path tail starting at the segment AFTER pack_id.
    idx = p.parts.index(pack_id)
    tail = p.parts[idx + 1 :]
    if not tail:
        return path
    url_path = "/".join(tail)
    # Strip any leading slashes from the prefix join.
    stripped_prefix = prefix.rstrip("/")
    return f"{stripped_prefix}/{pack_id}/{url_path}"


def _ensure_pathlike(value: str | Path) -> str:
    return str(value)
