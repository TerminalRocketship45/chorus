"""Wiring only. Every piece of logic lives in the stage modules."""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from chorus.align import WordTiming, align_words
from chorus.asr import transcribe
from chorus.l1.engine import is_accent_variant, load_ruleset
from chorus.miscue import detect_miscues, normalize
from chorus.scoring import score_reading, score_with_accent_excused
from chorus.types import Analysis, WordResult, WordStatus

_ALIGNABLE = re.compile(r"[a-z']*[a-z][a-z']*")


def apply_l1_filter(words: list[WordResult], language: str) -> list[WordResult]:
    """Mark substitutions that this reader's first language predicts.

    Raises KeyError for an unknown language, so a typo in a learner profile
    fails loudly rather than silently disabling the feature.
    """
    rules = load_ruleset(language)
    out: list[WordResult] = []
    for w in words:
        excused = (
            w.status is WordStatus.SUBSTITUTION
            and w.heard is not None
            and is_accent_variant(w.expected, w.heard, rules)
        )
        out.append(replace(w, accent_excused=excused))
    return out


def _is_alignable(token: str) -> bool:
    """True if the aligner can take this token: letters and apostrophes, at least one letter."""
    return _ALIGNABLE.fullmatch(token) is not None


def _attach_timings(
    words: list[WordResult],
    timings: list[WordTiming],
    aligned_indices: list[int],
) -> list[WordResult]:
    """Return new word results with alignment timings copied on.

    `timings[k]` belongs to the word whose index is `aligned_indices[k]`.
    Words that were not aligned (digits, hyphenated or non-ASCII tokens) are
    left untimed, and the pacing metric ignores untimed words.
    """
    if len(timings) != len(aligned_indices):
        raise ValueError(
            f"{len(timings)} timings for {len(aligned_indices)} aligned words"
        )
    by_index = dict(zip(aligned_indices, timings))
    out: list[WordResult] = []
    for w in words:
        t = by_index.get(w.index)
        out.append(replace(w, start=t.start, end=t.end) if t else replace(w))
    return out


def analyze(
    audio_path: str | Path,
    expected_text: str,
    language: str | None = None,
    model_size: str = "base.en",
) -> Analysis:
    """Score one read-aloud.

    `language` is the reader's home language. When given, the returned
    Analysis carries an accent-adjusted score alongside the raw one.
    """
    transcript = transcribe(audio_path, model_size=model_size)
    expected_tokens = normalize(expected_text)
    words = detect_miscues(expected_tokens, normalize(transcript.text))

    aligned_indices = [i for i, t in enumerate(expected_tokens) if _is_alignable(t)]
    if aligned_indices:
        timings = align_words(
            audio_path, " ".join(expected_tokens[i] for i in aligned_indices)
        )
        words = _attach_timings(words, timings, aligned_indices)

    raw = score_reading(words, duration_s=transcript.duration_s)
    adjusted = None
    if language:
        words = apply_l1_filter(words, language)
        adjusted = score_with_accent_excused(
            words, duration_s=transcript.duration_s
        )
    return Analysis(words=words, score=raw, accent_adjusted=adjusted)
