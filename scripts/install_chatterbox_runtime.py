"""Install and verify the hardware-appropriate Chatterbox voice runtime.

The Chatterbox PyPI dependency resolves to CPU-only PyTorch on Windows.  This
script runs after the normal profile install, detects NVIDIA driver capability,
and replaces only the version-matched Torch triplet with an official CUDA
wheel.  It also replaces the stale Perth wheel only when its real watermark
constructor is unavailable.  macOS keeps the ordinary wheel so Apple MPS
remains available.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Any

TORCH_VERSION = "2.6.0"
TORCHVISION_VERSION = "0.21.0"
TORCHAUDIO_VERSION = "2.6.0"
SUPPORTED_CHANNELS = ("auto", "cpu", "cu118", "cu124", "cu126")
PERTH_REVISION = "ce86c49d029f42272c1902eccb675556b9ed2330"
PERTH_ARCHIVE_URL = (
    "https://github.com/resemble-ai/Perth/archive/"
    f"{PERTH_REVISION}.zip"
)


@dataclass(frozen=True)
class NvidiaRuntime:
    available: bool
    name: str | None = None
    driver_cuda: tuple[int, int] | None = None
    compute_capability: tuple[int, int] | None = None


def _version_tuple(value: str) -> tuple[int, int] | None:
    match = re.search(r"(\d+)\.(\d+)", value)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _run_capture(command: list[str], *, timeout_s: float = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout_s,
    )


def detect_nvidia() -> NvidiaRuntime:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return NvidiaRuntime(available=False)
    summary = _run_capture([executable])
    if summary.returncode != 0:
        return NvidiaRuntime(available=False)
    cuda_match = re.search(
        r"CUDA\s+Version\s*:\s*(\d+\.\d+)",
        f"{summary.stdout}\n{summary.stderr}",
        re.IGNORECASE,
    )
    driver_cuda = _version_tuple(cuda_match.group(1)) if cuda_match else None

    query = _run_capture(
        [
            executable,
            "--query-gpu=name,compute_cap",
            "--format=csv,noheader,nounits",
        ]
    )
    name: str | None = None
    compute: tuple[int, int] | None = None
    if query.returncode == 0 and query.stdout.strip():
        first = query.stdout.splitlines()[0]
        parts = [part.strip() for part in first.split(",", maxsplit=1)]
        name = parts[0] or None
        if len(parts) == 2:
            compute = _version_tuple(parts[1])
    return NvidiaRuntime(
        available=True,
        name=name,
        driver_cuda=driver_cuda,
        compute_capability=compute,
    )


def select_channel(*, requested: str, system: str, nvidia: NvidiaRuntime) -> str | None:
    if requested not in SUPPORTED_CHANNELS:
        raise ValueError(f"unsupported Torch channel: {requested}")
    if requested != "auto":
        return requested
    if system == "Darwin":
        return None
    if not nvidia.available:
        return "cpu"
    blackwell_name = bool(
        nvidia.name and re.search(r"\b(?:RTX\s*50\d{2}|B\d{2,3}|GB\d{2,3})\b", nvidia.name, re.I)
    )
    if blackwell_name or (nvidia.compute_capability and nvidia.compute_capability >= (12, 0)):
        raise RuntimeError(
            "This NVIDIA GPU requires Blackwell-capable PyTorch, but Chatterbox 0.1.7 "
            "pins Torch 2.6.0. Use OPENMIMICRY_TORCH_CHANNEL=cpu temporarily or wait "
            "for a Chatterbox release supporting a newer Torch runtime."
        )
    supported = nvidia.driver_cuda
    if supported is None:
        # A working nvidia-smi with an unparseable banner is uncommon. cu118
        # is the least demanding official Torch 2.6 CUDA wheel.
        return "cu118"
    if supported >= (12, 6):
        return "cu126"
    if supported >= (12, 4):
        return "cu124"
    if supported >= (11, 8):
        return "cu118"
    raise RuntimeError(
        f"NVIDIA driver advertises CUDA {supported[0]}.{supported[1]}; "
        "Torch 2.6 requires CUDA 11.8 or newer. Update the NVIDIA driver."
    )


def probe_runtime(python: str) -> dict[str, Any]:
    code = (
        "import importlib.metadata as md, json, pathlib, torch, torchaudio, sounddevice, perth; "
        "from faster_whisper import WhisperModel; "
        "from chatterbox.tts_turbo import ChatterboxTurboTTS; "
        "mps=bool(getattr(torch.backends,'mps',None)) and torch.backends.mps.is_available(); "
        "print(json.dumps({'torch':torch.__version__,'torch_cuda':torch.version.cuda,"
        "'torchaudio':torchaudio.__version__,'torchvision':md.version('torchvision'),"
        "'chatterbox':md.version('chatterbox-tts'),"
        "'perth':md.version('resemble-perth'),"
        "'perth_watermarker_callable':callable(getattr(perth,'PerthImplicitWatermarker',None)),"
        "'perth_origin':str(pathlib.Path(perth.__file__).resolve()),"
        "'faster_whisper':md.version('faster-whisper'),"
        "'sounddevice':md.version('sounddevice'),"
        "'cuda_available':torch.cuda.is_available(),'mps_available':mps,"
        "'device':torch.cuda.get_device_name(0) if torch.cuda.is_available() else "
        "('Apple MPS' if mps else 'CPU')}))"
    )
    # A cold Chatterbox import can initialize CUDA libraries and inspect its
    # cache.  Give that probe substantially more time than nvidia-smi without
    # allowing an installation check to hang forever.
    completed = _run_capture([python, "-c", code], timeout_s=120)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "PyTorch runtime probe failed")
    try:
        value = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid PyTorch probe output: {completed.stdout[-500:]}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("PyTorch runtime probe did not return an object")
    return value


def diagnose_perth(python: str) -> str:
    """Expose the ImportError hidden by Perth's package-level fallback."""

    code = (
        "from perth.perth_net.perth_net_implicit.perth_watermarker "
        "import PerthImplicitWatermarker; "
        "assert callable(PerthImplicitWatermarker); "
        "print('PerthImplicitWatermarker imports OK')"
    )
    completed = _run_capture([python, "-c", code], timeout_s=120)
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    if completed.returncode == 0:
        return output or "PerthImplicitWatermarker imports OK"
    return output or f"direct Perth import failed with exit code {completed.returncode}"


def _runtime_matches(runtime: dict[str, Any], channel: str | None) -> bool:
    version = str(runtime.get("torch") or "")
    if (
        not version.startswith(TORCH_VERSION)
        or not str(runtime.get("torchaudio") or "").startswith(TORCHAUDIO_VERSION)
        or not str(runtime.get("torchvision") or "").startswith(TORCHVISION_VERSION)
        or runtime.get("chatterbox") != "0.1.7"
        or runtime.get("perth_watermarker_callable") is not True
    ):
        return False
    if channel is None:
        return True
    if channel == "cpu":
        return runtime.get("torch_cuda") is None
    return bool(runtime.get("cuda_available")) and channel.removeprefix("cu") in str(
        runtime.get("torch_cuda") or ""
    ).replace(".", "")


def _working_installed_channel(runtime: dict[str, Any]) -> str | None:
    """Return the official channel of a complete, currently usable triplet."""

    if runtime.get("torch_cuda") is None:
        return "cpu" if _runtime_matches(runtime, "cpu") else None
    cuda_version = _version_tuple(str(runtime.get("torch_cuda") or ""))
    channels = {(11, 8): "cu118", (12, 4): "cu124", (12, 6): "cu126"}
    channel = channels.get(cuda_version)
    if channel and _runtime_matches(runtime, channel):
        return channel
    return None


def install_torch(python: str, channel: str) -> None:
    index_url = f"https://download.pytorch.org/whl/{channel}"
    command = [
        python,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--force-reinstall",
        "--no-deps",
        f"torch=={TORCH_VERSION}",
        f"torchvision=={TORCHVISION_VERSION}",
        f"torchaudio=={TORCHAUDIO_VERSION}",
        "--index-url",
        index_url,
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"official PyTorch {channel} installation failed with exit code {completed.returncode}"
        )


def install_perth(python: str) -> None:
    """Install the immutable upstream revision Chatterbox now consumes.

    The PyPI 1.0.1 wheel predates upstream's packaging/import corrections and
    can expose a ``None`` watermarker on newer Python environments.  Use the
    official MIT repository at a content-addressed commit, without asking pip
    to disturb the already verified Torch/audio dependency graph.
    """

    requirement = f"resemble-perth @ {PERTH_ARCHIVE_URL}"
    command = [
        python,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--force-reinstall",
        "--no-deps",
        requirement,
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            "the pinned official Perth compatibility revision could not be installed "
            f"(exit code {completed.returncode})"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--channel",
        choices=SUPPORTED_CHANNELS,
        default=os.environ.get("OPENMIMICRY_TORCH_CHANNEL", "auto"),
    )
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    report: dict[str, Any] = {
        "passed": False,
        "system": platform.system(),
        "python": args.python,
        "requested_channel": args.channel,
    }
    try:
        nvidia = detect_nvidia()
        report["nvidia"] = asdict(nvidia)
        channel = select_channel(
            requested=args.channel,
            system=platform.system(),
            nvidia=nvidia,
        )
        report["selected_channel"] = channel or "platform-default"
        try:
            before = probe_runtime(args.python)
        except Exception as exc:
            report["before_error"] = f"{type(exc).__name__}: {exc}"
            if args.check_only:
                raise
            if channel is None:
                raise RuntimeError(
                    "The platform-default PyTorch runtime could not be imported; "
                    "reinstall the openrouter-chatterbox profile."
                ) from exc
            install_torch(args.python, channel)
        else:
            report["before"] = before
            if before.get("perth_watermarker_callable") is not True:
                report["perth_diagnostic"] = diagnose_perth(args.python)
                if args.check_only:
                    raise RuntimeError(
                        "Perth's real audio-watermark implementation is unavailable; "
                        "run the ordinary openrouter-chatterbox installer to repair it"
                    )
                install_perth(args.python)
                before = probe_runtime(args.python)
                report["after_perth_repair"] = before
                if before.get("perth_watermarker_callable") is not True:
                    report["perth_diagnostic_after_repair"] = diagnose_perth(args.python)
                    raise RuntimeError(
                        "Perth's real audio-watermark implementation is still unavailable "
                        "after the pinned compatibility repair"
                    )
            # Some Windows nvidia-smi builds omit the banner's CUDA version.
            # A complete CUDA triplet that already imports and sees the GPU is
            # stronger evidence than guessing cu118 and downloading a large
            # downgrade.
            installed_channel = _working_installed_channel(before)
            can_reuse_installed = (
                args.channel == "auto"
                and platform.system() != "Darwin"
                and (
                    (nvidia.available and installed_channel not in {None, "cpu"})
                    or (not nvidia.available and installed_channel == "cpu")
                )
            )
            if can_reuse_installed:
                assert installed_channel is not None
                channel = installed_channel
                report["selected_channel"] = channel
                report["selection_reason"] = "existing verified runtime"
            if not _runtime_matches(before, channel):
                if args.check_only:
                    raise RuntimeError(
                        f"PyTorch runtime does not match {channel or 'the platform default'}"
                    )
                if channel is None:
                    raise RuntimeError(
                        "The platform-default PyTorch runtime has an unexpected version; "
                        "reinstall the openrouter-chatterbox profile."
                    )
                install_torch(args.python, channel)
        after = probe_runtime(args.python)
        report["after"] = after
        if not _runtime_matches(after, channel):
            raise RuntimeError(
                f"PyTorch verification still does not match {channel or 'the platform default'}"
            )
        report["passed"] = True
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(report, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
