from __future__ import annotations

from types import SimpleNamespace

import pytest
from openmimicry.voice.workers.chatterbox_job import (
    _install_numpy2_reference_compat,
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
