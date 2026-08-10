"""Persistent, newline-delimited JSON worker for Chatterbox synthesis."""

from __future__ import annotations

import argparse
import functools
import json
import sys
import traceback
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _send(value: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _install_numpy2_reference_compat(model_type: type[Any]) -> bool:
    """Keep Chatterbox 0.1.7 reference conditioning in float32.

    Chatterbox 0.1.7's ``norm_loudness`` multiplies a float32 waveform by a
    NumPy float64 scalar.  NumPy 2 promotes the result to float64 and the next
    Torch operation fails with ``expected scalar type Double but found
    Float``.  Keep this narrowly scoped shim in the disposable worker until
    the upstream fix is released; never modify the installed third-party
    package in place.
    """

    import numpy as np  # type: ignore[import-not-found]

    original = getattr(model_type, "norm_loudness", None)
    if not callable(original):
        return False
    if bool(getattr(original, "__openmimicry_float32_compat__", False)):
        return False

    @functools.wraps(original)
    def norm_loudness_float32(self: Any, wav: Any, *args: Any, **kwargs: Any) -> Any:
        normalized = original(self, wav, *args, **kwargs)
        if isinstance(normalized, np.ndarray) and np.issubdtype(normalized.dtype, np.floating):
            return normalized.astype(np.float32, copy=False)
        return normalized

    norm_loudness_float32.__openmimicry_float32_compat__ = True  # type: ignore[attr-defined]
    model_type.norm_loudness = norm_loudness_float32  # type: ignore[attr-defined]
    return True


def _normalize_synthesis_text(value: str) -> str:
    """Return deterministic, tokenizer-safe text for a synthesis request.

    Tool results can contain invisible control/format characters copied from
    operating-system APIs.  They are valid JSON strings but are not useful to
    a speech tokenizer.  Preserve ordinary newlines/tabs as spaces and remove
    the remaining Unicode control characters before Chatterbox sees them.
    """

    normalized = unicodedata.normalize("NFKC", value)
    cleaned = "".join(
        " " if character in "\r\n\t" else character
        for character in normalized
        if character in "\r\n\t" or not unicodedata.category(character).startswith("C")
    )
    return " ".join(cleaned.split()).strip()


class _ScalarTokenizerCompat:
    """Retry the narrow Transformers scalar-tokenizer failure as a batch.

    Chatterbox Turbo calls a Hugging Face tokenizer with one string.  Some
    compatible ``tokenizers``/``transformers`` combinations intermittently
    reject that scalar at the Rust boundary with ``TextEncodeInput`` while
    accepting the semantically equivalent one-item batch.  Keep the workaround
    local to this disposable worker and only retry that exact TypeError.
    """

    __openmimicry_scalar_compat__ = True

    def __init__(self, tokenizer: Any) -> None:
        self._tokenizer = tokenizer

    def __call__(self, text: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return self._tokenizer(text, *args, **kwargs)
        except TypeError as exc:
            if not isinstance(text, str) or "TextEncodeInput" not in str(exc):
                raise
            return self._tokenizer([text], *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._tokenizer, name)


def _install_scalar_tokenizer_compat(model: Any) -> bool:
    tokenizer = getattr(model, "tokenizer", None)
    if tokenizer is None or bool(getattr(tokenizer, "__openmimicry_scalar_compat__", False)):
        return False
    model.tokenizer = _ScalarTokenizerCompat(tokenizer)
    return True


def _require_perth_watermarker(
    perth_module: Any | None = None,
    *,
    direct_loader: Callable[[], Any] | None = None,
) -> Any:
    """Return a real Perth constructor or fail with the suppressed import cause.

    ``resemble-perth`` 1.0.1 catches ``ImportError`` at package import time and
    publishes ``PerthImplicitWatermarker = None``.  Chatterbox 0.1.7 then calls
    that value unconditionally, replacing the useful dependency error with a
    misleading ``'NoneType' object is not callable``.  Retry the implementation
    import directly, patch the already-imported module when it succeeds, and
    never substitute Perth's dummy/no-watermark implementation.
    """

    if perth_module is None:
        import perth as perth_module  # type: ignore[import-not-found,no-redef]

    constructor = getattr(perth_module, "PerthImplicitWatermarker", None)
    if callable(constructor):
        return constructor

    try:
        if direct_loader is None:
            from perth.perth_net.perth_net_implicit.perth_watermarker import (  # type: ignore[import-not-found]
                PerthImplicitWatermarker,
            )

            constructor = PerthImplicitWatermarker
        else:
            constructor = direct_loader()
    except Exception as exc:
        raise RuntimeError(
            "Perth's real audio-watermark implementation could not be imported: "
            f"{type(exc).__name__}: {exc}. Reinstall the ordinary "
            "openrouter-chatterbox profile so OpenMimicry can apply its pinned "
            "Perth compatibility revision."
        ) from exc

    if not callable(constructor):
        raise RuntimeError(
            "Perth's real audio-watermark implementation resolved to a non-callable value. "
            "Reinstall the ordinary openrouter-chatterbox profile."
        )
    perth_module.PerthImplicitWatermarker = constructor
    return constructor


def _runtime_details(
    *, torch: Any, device: str, compat_applied: bool, tokenizer_compat: bool
) -> dict[str, object]:
    import numpy as np  # type: ignore[import-not-found]

    cuda_name: str | None = None
    if device == "cuda" and torch.cuda.is_available():
        cuda_name = str(torch.cuda.get_device_name(0))
    return {
        "device": device,
        "torch_version": str(torch.__version__),
        "torch_cuda": str(torch.version.cuda) if torch.version.cuda else None,
        "cuda_device": cuda_name,
        "numpy_version": str(np.__version__),
        "numpy2_compat": compat_applied,
        "tokenizer_scalar_compat": tokenizer_compat,
    }


def _select_device(torch: Any, requested: str) -> str:
    if requested != "auto":
        if requested == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA was requested but this PyTorch build cannot use CUDA. "
                "Run the OpenMimicry Chatterbox installer for a CUDA-enabled Torch wheel."
            )
        if requested == "mps" and not (
            bool(getattr(torch.backends, "mps", None)) and torch.backends.mps.is_available()
        ):
            raise RuntimeError("MPS was requested but is unavailable in this PyTorch build")
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if bool(getattr(torch.backends, "mps", None)) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _run_server(device_name: str, *, preflight_only: bool = False) -> int:
    try:
        import torch  # type: ignore[import-not-found]
        import torchaudio as ta  # type: ignore[import-not-found]

        _require_perth_watermarker()
        from chatterbox.tts_turbo import ChatterboxTurboTTS  # type: ignore[import-not-found]

        device = _select_device(torch, device_name)
        compat_applied = _install_numpy2_reference_compat(ChatterboxTurboTTS)
        model = ChatterboxTurboTTS.from_pretrained(device=device)
        tokenizer_compat = _install_scalar_tokenizer_compat(model)
        _send(
            {
                "type": "ready",
                "sample_rate": model.sr,
                **_runtime_details(
                    torch=torch,
                    device=device,
                    compat_applied=compat_applied,
                    tokenizer_compat=tokenizer_compat,
                ),
            }
        )
    except Exception as exc:
        _send(
            {
                "type": "error",
                "code": "startup_failed",
                "message": f"{type(exc).__name__}: {exc}",
            }
        )
        traceback.print_exc(file=sys.stderr)
        return 2

    if preflight_only:
        return 0

    for raw_line in sys.stdin:
        try:
            request: Any = json.loads(raw_line)
            if not isinstance(request, dict) or request.get("type") != "synthesize":
                raise ValueError("unsupported worker request")
            text = request.get("text")
            reference = request.get("reference")
            output = request.get("output")
            if not all(isinstance(item, str) and item for item in (text, reference, output)):
                raise ValueError("text, reference, and output must be non-empty strings")
            text = _normalize_synthesis_text(text)
            if not text:
                raise ValueError("text contains no speakable characters")
            reference_path = Path(reference).resolve()
            output_path = Path(output).resolve()
            if not reference_path.is_file():
                raise ValueError("reference recording does not exist")
            if reference_path.suffix.casefold() not in {".wav", ".mp3"}:
                raise ValueError("reference recording must be WAV or MP3")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            wave = model.generate(text, audio_prompt_path=str(reference_path))
            if hasattr(wave, "is_floating_point") and wave.is_floating_point():
                wave = wave.to(dtype=torch.float32)
            ta.save(str(output_path), wave, model.sr)
            _send({"type": "complete"})
        except Exception as exc:
            _send(
                {
                    "type": "error",
                    "code": "synthesis_failed",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )
            traceback.print_exc(file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--server", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda", "mps"))
    args = parser.parse_args()
    return _run_server(args.device, preflight_only=args.preflight)


if __name__ == "__main__":
    raise SystemExit(main())
