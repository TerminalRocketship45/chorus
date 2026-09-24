"""Reading fluency metrics.

WCPM (words correct per minute) is the standard oral reading fluency measure
and is what teacher-administered running records report.
"""
from __future__ import annotations

from chorus.types import ERROR_STATUSES, ReadingScore, WordResult


def score_reading(
    words: list[WordResult], duration_s: float, long_pause_s: float = 1.0
) -> ReadingScore:
    """Score a read, counting every error status against accuracy."""
    return _score(words, duration_s, long_pause_s, excuse_accents=False)


def score_with_accent_excused(
    words: list[WordResult], duration_s: float, long_pause_s: float = 1.0
) -> ReadingScore:
    """Score a read, treating accent-excused words as correct."""
    return _score(words, duration_s, long_pause_s, excuse_accents=True)


def _score(
    words: list[WordResult],
    duration_s: float,
    long_pause_s: float,
    excuse_accents: bool,
) -> ReadingScore:
    total = len(words)
    correct = sum(
        1
        for w in words
        if w.status not in ERROR_STATUSES or (excuse_accents and w.accent_excused)
    )
    accuracy = correct / total if total else 0.0
    wcpm = (correct / duration_s) * 60.0 if duration_s > 0 else 0.0
    return ReadingScore(
        accuracy=accuracy,
        wcpm=wcpm,
        total_words=total,
        correct_words=correct,
        duration_s=duration_s,
        long_pauses=_count_long_pauses(words, long_pause_s),
    )


def _count_long_pauses(words: list[WordResult], long_pause_s: float) -> int:
    """Count gaps between consecutive timed words that exceed the threshold."""
    timed = [w for w in words if w.start is not None and w.end is not None]
    return sum(
        1
        for prev, nxt in zip(timed, timed[1:])
        if (nxt.start - prev.end) >= long_pause_s
    )
