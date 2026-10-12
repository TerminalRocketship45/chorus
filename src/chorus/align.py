"""Forced alignment of audio against the expected passage text.

This is deliberately separate from ASR. ASR answers "what did they say";
alignment answers "when did they say each expected word". Timings feed the
pacing metric. The per-word score is a match-quality signal between the audio
and the expected word that the Phase 1 pipeline does not yet propagate to
WordResult.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

TARGET_SR = 16000
# Permissive callee contract; pipeline._ALIGNABLE is the stricter caller filter
# (it also requires at least one letter). Keep the two in step.
_ALIGNABLE = re.compile(r"[a-z']+")


@dataclass
class WordTiming:
    word: str
    start: float
    end: float
    score: float


@lru_cache(maxsize=1)
def _get_bundle():
    """Load and cache the MMS forced-alignment bundle."""
    import torchaudio

    return torchaudio.pipelines.MMS_FA


@lru_cache(maxsize=1)
def _get_device() -> str:
    """Pick "cuda" when available, else "cpu" (the default on a CPU-only machine)."""
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=1)
def _get_model_bundle():
    """Build and cache the model, tokenizer and aligner (the ~2 s rebuild cost).

    This is the actual fix for the "rebuilds on every call" cost: `_get_bundle`
    above only memoises the (cheap) bundle *descriptor* lookup, not the
    (expensive) `bundle.get_model()` call that constructs and loads weights.
    Cached once per process, keyed on nothing (there is only one bundle), so
    a changed device after the first call has no effect until the process
    restarts — the same lifetime contract as asr._get_model.
    """
    bundle = _get_bundle()
    device = _get_device()
    model = bundle.get_model().to(device)
    tokenizer = bundle.get_tokenizer()
    aligner = bundle.get_aligner()
    return model, tokenizer, aligner, device


def _load_audio(path: Path, device: str = "cpu"):
    """Load audio as mono 16 kHz float32 on `device`, resampling if needed."""
    import torch
    import torchaudio

    waveform, sr = torchaudio.load(str(path))
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if sr != TARGET_SR:
        waveform = torchaudio.functional.resample(waveform, sr, TARGET_SR)
    return waveform.to(torch.float32).to(device)


def align_words(audio_path: str | Path, expected_text: str) -> list[WordTiming]:
    """Return one timing per whitespace-separated word in `expected_text`.

    Input words must match ``^[a-z']+$`` after lowercasing (letters and
    apostrophes only, which is all the MMS_FA dictionary accepts); anything
    else raises ValueError naming the offending tokens. Exactly one
    WordTiming is returned per word. Audio much shorter than the text does
    not raise but yields squeezed timings with scores near 0, so `score` is
    the mismatch signal.
    """
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")
    words = expected_text.lower().split()
    if not words:
        return []
    bad = [w for w in words if not _ALIGNABLE.fullmatch(w)]
    if bad:
        raise ValueError(
            f"cannot align tokens with characters outside a-z and ': {bad}"
        )

    import torch

    model, tokenizer, aligner, device = _get_model_bundle()

    waveform = _load_audio(path, device)
    with torch.inference_mode():
        emission, _ = model(waveform)
        token_spans = aligner(emission[0], tokenizer(words))

    if len(token_spans) != len(words):
        raise RuntimeError(
            f"aligner returned {len(token_spans)} spans for {len(words)} words"
        )

    ratio = waveform.shape[1] / emission.shape[1] / TARGET_SR
    return [
        WordTiming(
            word=word,
            start=spans[0].start * ratio,
            end=spans[-1].end * ratio,
            score=sum(s.score for s in spans) / len(spans),
        )
        for word, spans in zip(words, token_spans)
    ]
