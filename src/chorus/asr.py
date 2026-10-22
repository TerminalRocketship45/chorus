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
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


@dataclass
class Segment:
    """One recognised stretch of speech, with Whisper's own confidence signals."""

    text: str
    start: float
    end: float
    no_speech_prob: float
    avg_logprob: float


@dataclass
class Transcript:
    text: str
    duration_s: float
    #: Every segment Whisper produced (before any hallucination filter), for diagnosis.
    segments: list[Segment] = field(default_factory=list)
    #: How many segments `drop_hallucinations` removed (0 when it is off).
    dropped_segments: int = 0


#: Whisper's own "this is silence" rule (openai/whisper transcribe.py): a segment is
#: treated as no speech when no_speech_prob is above 0.6 AND avg_logprob is below -1.0.
NO_SPEECH_THRESHOLD = 0.6
LOGPROB_THRESHOLD = -1.0
#: Measured on pure silence and noise: Whisper writes a lone "You" with no_speech_prob 0.92-0.94
#: but a confident avg_logprob (-0.6 to -1.0), which Whisper's own two-signal rule misses.
SURE_NO_SPEECH = 0.9


def is_hallucinated(seg: Segment) -> bool:
    if seg.no_speech_prob > SURE_NO_SPEECH:
        return True
    return seg.no_speech_prob > NO_SPEECH_THRESHOLD and seg.avg_logprob < LOGPROB_THRESHOLD


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


def transcribe(
    audio_path: str | Path,
    model_size: str = "base.en",
    beam_size: int = 1,
    initial_prompt: str | None = None,
    hotwords: str | None = None,
    vad_filter: bool = False,
    drop_hallucinations: bool = False,
) -> Transcript:
    """Transcribe an audio file. Returns what was said, not what was expected.

    Defaults reproduce the shipped behaviour (greedy decoding, no prompt).
    beam_size > 1 is slower (roughly 2x on CPU). initial_prompt / hotwords bias
    the recogniser towards given text; passing the expected passage can make
    it write the expected word even when the reader said something else, so
    it is opt-in and must be checked against genuine-error retention.
    vad_filter runs Silero voice-activity detection first so silence and noise are
    never decoded (the usual source of invented text on a silent recording).
    drop_hallucinations discards segments Whisper itself flags as silence
    (see `is_hallucinated`); both are off by default.
    """
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")
    model = _get_model(model_size)
    segments, info = model.transcribe(
        str(path),
        language="en",
        beam_size=beam_size,
        initial_prompt=initial_prompt,
        hotwords=hotwords,
        vad_filter=vad_filter,
    )
    segs = [
        Segment(
            text=seg.text.strip(),
            start=float(seg.start),
            end=float(seg.end),
            no_speech_prob=float(seg.no_speech_prob),
            avg_logprob=float(seg.avg_logprob),
        )
        for seg in segments
    ]
    kept = [g for g in segs if not (drop_hallucinations and is_hallucinated(g))]
    text = " ".join(g.text for g in kept).strip()
    return Transcript(
        text=text,
        duration_s=float(info.duration),
        segments=segs,
        dropped_segments=len(segs) - len(kept),
    )
