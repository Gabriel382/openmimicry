"""Select and prove a Faster-Whisper runtime with safe automatic fallback."""

from __future__ import annotations

import ctypes
import platform
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, TypeVar

__all__ = [
    "WhisperRuntime",
    "cuda_runtime_probe",
    "load_whisper_runtime",
    "run_with_auto_cpu_fallback",
]


@dataclass(frozen=True)
class WhisperRuntime:
    """Loaded inference engine and the hardware choice that actually worked."""

    model: Any
    device: str
    compute_type: str
    fallback_reason: str | None = None


def cuda_runtime_probe(
    *,
    system: str | None = None,
    dll_loader: Callable[[str], object] | None = None,
) -> tuple[bool, str | None]:
    """Prove the native CUDA libraries CTranslate2 needs on Windows.

    ``get_cuda_device_count`` only proves that an NVIDIA driver can enumerate
    the GPU.  CTranslate2 4.x Windows wheels additionally require CUDA 12
    cuBLAS and, for Whisper, cuDNN 8.  Model construction is lazy enough that
    those DLL failures otherwise appear on the first real utterance.  In auto
    mode we select the guaranteed CPU lane before recording instead.

    Explicit ``device=cuda`` remains strict and is not downgraded by this
    probe, so an operator can diagnose or require a GPU installation.
    """

    current_system = system or platform.system()
    if current_system != "Windows":
        return True, None
    loader = dll_loader or ctypes.WinDLL  # type: ignore[attr-defined]
    missing: list[str] = []
    for library in ("cublas64_12.dll", "cudnn64_8.dll"):
        try:
            loader(library)
        except (OSError, AttributeError):
            missing.append(library)
    if not missing:
        return True, None
    return (
        False,
        "CUDA 12 speech libraries are unavailable ("
        + ", ".join(missing)
        + "); selected the compatible CPU/INT8 runtime",
    )


def load_whisper_runtime(
    model_name: str,
    *,
    requested_device: str = "auto",
    requested_compute_type: str = "auto",
    model_class: Any | None = None,
    cuda_count: Callable[[], int] | None = None,
    cuda_probe: Callable[[], tuple[bool, str | None]] | None = None,
) -> WhisperRuntime:
    """Load Faster-Whisper, falling back only when ``device`` is ``auto``.

    CTranslate2 can report an NVIDIA device even when required CUDA DLLs such
    as ``cublas64_12.dll`` are absent. Device enumeration is therefore only a
    hint: model construction must also succeed before CUDA is accepted.
    """

    if model_class is None:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]

        model_class = WhisperModel
    device = requested_device
    detection_error: str | None = None
    if device == "auto":
        if cuda_count is None:
            import ctranslate2  # type: ignore[import-not-found]

            cuda_count = ctranslate2.get_cuda_device_count
        try:
            device = "cuda" if cuda_count() > 0 else "cpu"
        except Exception as exc:
            device = "cpu"
            detection_error = _failure_text(exc)
        if device == "cuda":
            usable, reason = (cuda_probe or cuda_runtime_probe)()
            if not usable:
                device = "cpu"
                detection_error = reason or "CUDA speech runtime is unavailable"
    compute_type = requested_compute_type
    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"

    try:
        model = model_class(model_name, device=device, compute_type=compute_type)
    except Exception as exc:
        if requested_device != "auto" or device != "cuda":
            raise
        reason = _failure_text(exc)
        model = model_class(model_name, device="cpu", compute_type="int8")
        return WhisperRuntime(
            model=model,
            device="cpu",
            compute_type="int8",
            fallback_reason=f"CUDA model load failed; using CPU/INT8: {reason}",
        )

    return WhisperRuntime(
        model=model,
        device=device,
        compute_type=compute_type,
        fallback_reason=(detection_error),
    )


_ResultT = TypeVar("_ResultT")


def run_with_auto_cpu_fallback(
    runtime: WhisperRuntime,
    *,
    model_name: str,
    requested_device: str,
    operation: Callable[[Any], _ResultT],
) -> tuple[_ResultT, WhisperRuntime]:
    """Run one inference and retry on CPU if an auto-selected CUDA lane fails."""

    try:
        return operation(runtime.model), runtime
    except Exception as exc:
        if requested_device != "auto" or runtime.device != "cuda":
            raise
        fallback = load_whisper_runtime(
            model_name,
            requested_device="cpu",
            requested_compute_type="int8",
        )
        fallback = replace(
            fallback,
            fallback_reason=f"CUDA inference failed; using CPU/INT8: {_failure_text(exc)}",
        )
        return operation(fallback.model), fallback


def _failure_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"
