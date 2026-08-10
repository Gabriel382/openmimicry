from __future__ import annotations

from types import SimpleNamespace

import pytest
from openmimicry.voice.workers.chatterbox_job import (
    _install_numpy2_reference_compat,
    _install_scalar_tokenizer_compat,
    _normalize_synthesis_text,
    _require_perth_watermarker,
    _select_device,
)


def test_numpy2_reference_compat_returns_float32_and_is_idempotent() -> None:
    np = pytest.importorskip("numpy")

    class FakeChatterbox:
        def norm_loudness(self, wav, _sr):
            return wav * np.float64(1.25)

    assert _install_numpy2_reference_compat(FakeChatterbox) is True
    conditioned = FakeChatterbox().norm_loudness(np.ones(8, dtype=np.float32), 24_000)

    assert conditioned.dtype == np.float32
    assert _install_numpy2_reference_compat(FakeChatterbox) is False


def test_scalar_tokenizer_compat_retries_exact_failure_as_one_item_batch() -> None:
    class Tokenizer:
        def __init__(self) -> None:
            self.values = []

        def __call__(self, value, **_kwargs):
            self.values.append(value)
            if isinstance(value, str):
                raise TypeError(
                    "TextEncodeInput must be Union[TextInputSequence, "
                    "Tuple[InputSequence, InputSequence]]"
                )
            return {"input_ids": [[1, 2, 3]]}

    tokenizer = Tokenizer()
    model = SimpleNamespace(tokenizer=tokenizer)

    assert _install_scalar_tokenizer_compat(model) is True
    assert model.tokenizer("Alarm set for 17:00.") == {"input_ids": [[1, 2, 3]]}
    assert tokenizer.values == ["Alarm set for 17:00.", ["Alarm set for 17:00."]]
    assert _install_scalar_tokenizer_compat(model) is False


def test_synthesis_text_normalization_removes_hidden_tool_controls() -> None:
    assert _normalize_synthesis_text("Alarm\x00 set\nfor 17:00.\u200b") == "Alarm set for 17:00."


def test_requested_cuda_fails_before_model_load_when_torch_is_cpu_only() -> None:
    torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)),
    )

    with pytest.raises(RuntimeError, match="cannot use CUDA"):
        _select_device(torch, "cuda")


def test_perth_compat_restores_the_real_constructor_without_dummy_fallback() -> None:
    class RealWatermarker:
        pass

    perth = SimpleNamespace(PerthImplicitWatermarker=None)

    resolved = _require_perth_watermarker(
        perth,
        direct_loader=lambda: RealWatermarker,
    )

    assert resolved is RealWatermarker
    assert perth.PerthImplicitWatermarker is RealWatermarker


def test_perth_compat_surfaces_the_hidden_import_error() -> None:
    perth = SimpleNamespace(PerthImplicitWatermarker=None)

    def fail_import():
        raise ImportError("missing watermark dependency")

    with pytest.raises(RuntimeError, match="missing watermark dependency"):
        _require_perth_watermarker(perth, direct_loader=fail_import)
