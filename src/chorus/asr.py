"""Speech recognition adapter.

Isolates faster-whisper so the rest of the engine never imports it directly.
faster-whisper is chosen over openai-whisper because this project must run
inference on CPU; CTranslate2 is several times faster there.

Model sizing: base.en for tests, small.en for real runs. Never medium — it
will not fit the 2GB GPU and is slow on CPU.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass
class Transcript:
    text: str
    duration_s: float


@lru_cache(maxsize=2)
def _get_model(model_size: str):
    """Load and cache a Whisper model. int8 keeps CPU inference tractable."""
    from faster_whisper import WhisperModel

    return WhisperModel(model_size, device="cpu", compute_type="int8")


def transcribe(audio_path: str | Path, model_size: str = "base.en") -> Transcript:
    """Transcribe an audio file. Returns what was said, not what was expected."""
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    model = _get_model(model_size)
    segments, info = model.transcribe(str(path), language="en", beam_size=1)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return Transcript(text=text, duration_s=float(info.duration))
