from __future__ import annotations

import platform
from pathlib import Path

import pytest

from scripts.install_chatterbox_runtime import (
    PERTH_REVISION,
    NvidiaRuntime,
    _runtime_matches,
    _runtime_mismatches,
    _working_installed_channel,
    main,
    select_channel,
)


@pytest.mark.parametrize(
    ("driver_cuda", "expected"),
    [
        ((13, 0), "cu126"),
        ((12, 6), "cu126"),
        ((12, 4), "cu124"),
        ((11, 8), "cu118"),
    ],
)
def test_auto_channel_tracks_nvidia_driver_capability(driver_cuda, expected) -> None:
    nvidia = NvidiaRuntime(available=True, driver_cuda=driver_cuda)

    assert select_channel(requested="auto", system="Windows", nvidia=nvidia) == expected


def test_auto_channel_keeps_platform_default_on_macos() -> None:
    assert (
        select_channel(
            requested="auto",
            system="Darwin",
            nvidia=NvidiaRuntime(available=False),
        )
        is None
    )


def test_blackwell_fails_closed_instead_of_installing_incompatible_torch() -> None:
    nvidia = NvidiaRuntime(
        available=True,
        name="NVIDIA GeForce RTX 5090",
        driver_cuda=(12, 8),
        compute_capability=(12, 0),
    )

    with pytest.raises(RuntimeError, match="Blackwell"):
        select_channel(requested="auto", system=platform.system(), nvidia=nvidia)


def test_cpu_channel_rejects_cuda_wheel_when_driver_is_unavailable() -> None:
    runtime = {
        "torch": "2.6.0+cu124",
        "torch_cuda": "12.4",
        "torchaudio": "2.6.0+cu124",
        "torchvision": "0.21.0",
        "chatterbox": "0.1.7",
        "perth_watermarker_callable": True,
        "cuda_available": False,
    }

    assert _runtime_matches(runtime, "cpu") is False


def test_runtime_requires_version_matched_torch_triplet() -> None:
    runtime = {
        "torch": "2.6.0+cpu",
        "torch_cuda": None,
        "torchaudio": "2.6.0+cpu",
        "torchvision": "0.20.0",
        "chatterbox": "0.1.7",
        "perth_watermarker_callable": True,
        "cuda_available": False,
    }

    assert _runtime_matches(runtime, "cpu") is False


def test_cuda_build_suffixes_are_valid_version_matched_triplet() -> None:
    runtime = {
        "torch": "2.6.0+cu126",
        "torch_cuda": "12.6",
        "torchaudio": "2.6.0+cu126",
        "torchvision": "0.21.0+cu126",
        "chatterbox": "0.1.7",
        "perth_watermarker_callable": True,
        "cuda_available": True,
    }

    assert _runtime_matches(runtime, "cu126") is True
    assert _working_installed_channel(runtime) == "cu126"


def test_installer_does_not_force_reinstall_unrelated_dependencies() -> None:
    installer = Path(__file__).resolve().parents[3] / "scripts/install_chatterbox_runtime.py"
    source = installer.read_text(encoding="utf-8")

    assert '"--no-deps"' in source
    assert PERTH_REVISION in source
    assert "Perth/archive" in source


def test_runtime_rejects_perth_none_constructor() -> None:
    runtime = {
        "torch": "2.6.0+cu118",
        "torch_cuda": "11.8",
        "torchaudio": "2.6.0+cu118",
        "torchvision": "0.21.0+cu118",
        "chatterbox": "0.1.7",
        "perth_watermarker_callable": False,
        "cuda_available": True,
    }

    assert _runtime_matches(runtime, "cu118") is False


def test_installer_repairs_perth_before_accepting_runtime(monkeypatch, capsys) -> None:
    bad = {
        "torch": "2.6.0+cpu",
        "torch_cuda": None,
        "torchaudio": "2.6.0+cpu",
        "torchvision": "0.21.0",
        "chatterbox": "0.1.7",
        "perth": "1.0.1",
        "perth_watermarker_callable": False,
        "cuda_available": False,
    }
    good = {**bad, "perth_watermarker_callable": True}
    probes = iter((bad, good, good))
    repairs: list[str] = []

    monkeypatch.setattr(
        "scripts.install_chatterbox_runtime.detect_nvidia",
        lambda: NvidiaRuntime(available=False),
    )
    monkeypatch.setattr(
        "scripts.install_chatterbox_runtime.probe_runtime",
        lambda _python: next(probes),
    )
    monkeypatch.setattr(
        "scripts.install_chatterbox_runtime.diagnose_perth",
        lambda _python: "ImportError: hidden cause",
    )
    monkeypatch.setattr(
        "scripts.install_chatterbox_runtime.install_perth",
        lambda python: repairs.append(python),
    )
    monkeypatch.setattr(
        "scripts.install_chatterbox_runtime.install_torch",
        lambda *_args: pytest.fail("a Perth repair must not reinstall Torch"),
    )
    monkeypatch.setattr("sys.argv", ["install_chatterbox_runtime.py", "--python", "python"])

    assert main() == 0
    assert repairs == ["python"]
    report = capsys.readouterr().out
    assert '"perth_diagnostic": "ImportError: hidden cause"' in report
    assert '"passed": true' in report


def test_installer_repairs_perth_after_initial_torch_import_failure(monkeypatch, capsys) -> None:
    """Regression for the reported torchvision::nms -> Perth false sequence."""

    after_torch = {
        "torch": "2.6.0+cu118",
        "torch_cuda": "11.8",
        "torchaudio": "2.6.0+cu118",
        "torchvision": "0.21.0+cu118",
        "chatterbox": "0.1.7",
        "perth": "1.0.1",
        "perth_watermarker_callable": False,
        "cuda_available": True,
    }
    after_perth = {**after_torch, "perth_watermarker_callable": True}
    probes = iter(
        (
            RuntimeError("operator torchvision::nms does not exist"),
            after_torch,
            after_perth,
            after_perth,
        )
    )
    torch_repairs: list[tuple[str, str]] = []
    perth_repairs: list[str] = []

    def probe(_python: str):
        value = next(probes)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(
        "scripts.install_chatterbox_runtime.detect_nvidia",
        lambda: NvidiaRuntime(
            available=True,
            name="NVIDIA GeForce RTX 4070 Laptop GPU",
            compute_capability=(8, 9),
        ),
    )
    monkeypatch.setattr("scripts.install_chatterbox_runtime.probe_runtime", probe)
    monkeypatch.setattr(
        "scripts.install_chatterbox_runtime.diagnose_perth",
        lambda _python: "TypeError: PerthImplicitWatermarker is not callable",
    )
    monkeypatch.setattr(
        "scripts.install_chatterbox_runtime.install_torch",
        lambda python, channel: torch_repairs.append((python, channel)),
    )
    monkeypatch.setattr(
        "scripts.install_chatterbox_runtime.install_perth",
        lambda python: perth_repairs.append(python),
    )
    monkeypatch.setattr("sys.argv", ["install_chatterbox_runtime.py", "--python", "python"])

    assert main() == 0
    assert torch_repairs == [("python", "cu118")]
    assert perth_repairs == ["python"]
    report = capsys.readouterr().out
    assert '"after_torch_repair"' in report
    assert '"after_perth_repair"' in report
    assert '"passed": true' in report
    assert "PyTorch verification still does not match" not in report


def test_runtime_mismatches_identify_perth_without_blaming_pytorch() -> None:
    runtime = {
        "torch": "2.6.0+cu118",
        "torch_cuda": "11.8",
        "torchaudio": "2.6.0+cu118",
        "torchvision": "0.21.0+cu118",
        "chatterbox": "0.1.7",
        "perth_watermarker_callable": False,
        "cuda_available": True,
    }

    assert _runtime_mismatches(runtime, "cu118") == ["PerthImplicitWatermarker is unavailable"]
