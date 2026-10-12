"""Speech recognition adapter.

Isolates faster-whisper so the rest of the engine never imports it directly.
faster-whisper is chosen over openai-whisper because it wraps CTranslate2,
which is several times faster than plain PyTorch inference on CPU and also
runs on CUDA.

Device selection is automatic by default (CUDA if CTranslate2 sees a GPU,
else CPU) and can be forced with the CHORUS_ASR_DEVICE env var (cpu|cuda|
auto). Compute type follows the device (float16 on cuda, int8 on cpu) and
can be overridden with CHORUS_ASR_COMPUTE_TYPE. See _resolve_device and
_resolve_compute_type below.

Model sizing: base.en for tests, small.en for real runs. medium has not been
sized for this project's GPU budget; measure before using it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass
class Transcript:
    text: str
    duration_s: float


def _resolve_device(cuda_device_count: int | None = None) -> str:
    """Pick "cpu" or "cuda" from CHORUS_ASR_DEVICE (default "auto").

    "auto" picks "cuda" when CTranslate2 reports at least one visible CUDA
    device, else "cpu". cuda_device_count lets tests pin the auto branch
    without touching ctranslate2 or a GPU; real callers leave it as None, and
    it is read from ctranslate2.get_cuda_device_count() lazily (only when
    needed) so this stays import-light on a CPU-only machine.
    """
    requested = os.environ.get("CHORUS_ASR_DEVICE", "auto").lower()
    if requested not in ("cpu", "cuda", "auto"):
        raise ValueError(
            f"CHORUS_ASR_DEVICE must be 'cpu', 'cuda', or 'auto', got {requested!r}"
        )
    if requested != "auto":
        return requested
    if cuda_device_count is None:
        import ctranslate2

        cuda_device_count = ctranslate2.get_cuda_device_count()
    return "cuda" if cuda_device_count > 0 else "cpu"


def _resolve_compute_type(device: str) -> str:
    """Pick a CTranslate2 compute type for the given device.

    float16 on cuda and int8 on cpu are the settings this project has
    measured; CHORUS_ASR_COMPUTE_TYPE overrides either (e.g. int8_float16 on
    a GPU with little VRAM).
    """
    override = os.environ.get("CHORUS_ASR_COMPUTE_TYPE")
    if override:
        return override
    return "float16" if device == "cuda" else "int8"


@lru_cache(maxsize=2)
def _get_model(model_size: str):
    """Load and cache a Whisper model, keyed by model_size only.

    Device and compute type are resolved once per cached model from
    CHORUS_ASR_DEVICE / CHORUS_ASR_COMPUTE_TYPE (see _resolve_device and
    _resolve_compute_type above); they are not part of the cache key, so
    changing those env vars after a model_size has already been loaded in
    this process has no effect until the process restarts.
    """
    from faster_whisper import WhisperModel

    device = _resolve_device()
    compute_type = _resolve_compute_type(device)
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def transcribe(audio_path: str | Path, model_size: str = "base.en") -> Transcript:
    """Transcribe an audio file. Returns what was said, not what was expected."""
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")
    model = _get_model(model_size)
    segments, info = model.transcribe(str(path), language="en", beam_size=1)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return Transcript(text=text, duration_s=float(info.duration))
