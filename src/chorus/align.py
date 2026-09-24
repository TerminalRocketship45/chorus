"""Forced alignment of audio against the expected passage text.

This is deliberately separate from ASR. ASR answers "what did they say";
alignment answers "when did they say each expected word". Timings feed the
pacing metric, and the per-word confidence scores flag words the reader
struggled to produce even when the word itself was right.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

TARGET_SR = 16000
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


def _load_audio(path: Path):
    """Load audio as mono 16 kHz float32, resampling if needed."""
    import torch
    import torchaudio

    waveform, sr = torchaudio.load(str(path))
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if sr != TARGET_SR:
        waveform = torchaudio.functional.resample(waveform, sr, TARGET_SR)
    return waveform.to(torch.float32)


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
    if not path.exists():
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
    import torchaudio.functional as F

    bundle = _get_bundle()
    model = bundle.get_model()
    tokenizer = bundle.get_tokenizer()
    aligner = bundle.get_aligner()

    waveform = _load_audio(path)
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
