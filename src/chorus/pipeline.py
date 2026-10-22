"""Wiring only. Every piece of logic lives in the stage modules.

An accent-excused SUBSTITUTION keeps its status and still counts as an error
in the RAW score; consumers must render `accent_excused` words as correct and
never describe an accent as wrong.
"""
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

# Stricter caller filter (requires a letter); align._ALIGNABLE, `[a-z']+`, is the
# permissive callee contract. Keep the two in step.
_ALIGNABLE = re.compile(r"[a-z']*[a-z][a-z']*")


def apply_l1_filter(words: list[WordResult], language: str) -> list[WordResult]:
    """Mark substitutions that this reader's first language predicts.

    Raises KeyError for an unknown language, so a typo in a learner profile
    fails loudly rather than silently disabling the feature. Excused words keep
    their SUBSTITUTION status and still count as errors in the raw score.
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
    Words that were not aligned (tokens like 2599, hyphenated or non-ASCII tokens) are
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
    beam_size: int = 1,
    same_sound: bool = False,
    prompt_passage: bool = False,
    digit_context: bool = False,
) -> Analysis:
    """Score one read-aloud.

    Opt-in recogniser options (defaults reproduce the shipped behaviour):
    `beam_size` (decoding beam), `same_sound` (homophone spellings such as
    two/too count as correct) and `digit_context` (digit runs such as 495 may read digit-by-digit if the
    passage does), and `prompt_passage` (give Whisper the passage
    as `initial_prompt`; can hide genuine errors, see eval/).

    `language` is the reader's home language. When given, the returned
    Analysis carries an accent-adjusted score alongside the raw one, and an
    unknown language raises KeyError before any model runs. `duration_s` and
    WCPM use the whole recording, so leading and trailing silence lowers WCPM.
    Omitted and unalignable words are untimed (start/end None).
    """
    if language:
        load_ruleset(language)
    expected_tokens = normalize(expected_text)
    if not expected_tokens:
        raise ValueError("expected_text contains no words")
    asr_opts: dict = {}
    if beam_size != 1:
        asr_opts["beam_size"] = beam_size
    if prompt_passage:
        asr_opts["initial_prompt"] = expected_text
    transcript = transcribe(audio_path, model_size=model_size, **asr_opts)
    words = detect_miscues(
        expected_tokens,
        normalize(
            transcript.text, digit_context=expected_tokens if digit_context else None
        ),
        **({"same_sound": True} if same_sound else {}),
    )

    aligned_indices = [
        w.index
        for w in words
        if w.status is not WordStatus.OMISSION and _is_alignable(w.expected)
    ]
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
