"""Runtime response-presentation settings exposed to the local dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Request
from openmimicry.core.schemas.app import ResponsePresentationConfig

from ..user_settings import persist_interaction_settings

__all__ = ["router"]


router = APIRouter()


@router.get("/interaction/settings")
async def interaction_settings(request: Request) -> dict[str, object]:
    current: ResponsePresentationConfig = request.app.state.presentation_state["value"]
    return current.model_dump(mode="json")


@router.post("/interaction/settings")
async def update_interaction_settings(
    values: ResponsePresentationConfig, request: Request
) -> dict[str, object]:
    request.app.state.presentation_state["value"] = values
    persist_interaction_settings(values.model_dump(mode="json"))

    appearance = request.app.state.appearance
    request.app.state.appearance = appearance.model_copy(
        update={
            "behaviour": appearance.behaviour.model_copy(
                update={
                    "bubble": appearance.behaviour.bubble.model_copy(
                        update={
                            "base_ms": values.base_ms,
                            "ms_per_character": values.ms_per_character,
                            "min_ms": values.minimum_ms,
                            "max_ms": values.maximum_ms,
                        }
                    )
                }
            )
        }
    )
    return values.model_dump(mode="json")
