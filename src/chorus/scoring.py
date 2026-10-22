"""Reading fluency metrics.

WCPM (words correct per minute) is the standard oral reading fluency measure
and is what teacher-administered running records report.

Notes on WCPM: the duration_s parameter is the elapsed time of the whole
recording as supplied by the caller. WCPM is calculated as:
  WCPM = (correct_words / duration_s) * 60

Leading or trailing silence in the recording lowers WCPM. Callers wanting
the standard first-word-to-last-word figure must pass a trimmed duration.
"""
from __future__ import annotations

from chorus.types import ERROR_STATUSES, ReadingScore, WordResult, WordStatus


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
    """Score the reading passage.

    The duration_s parameter is the elapsed time of the whole recording
    as supplied by the caller. WCPM = correct_words / duration_s * 60.
    Leading or trailing silence therefore lowers WCPM; callers wanting
    the standard first-word-to-last-word figure must pass a trimmed duration.
    """
    passage_total = len(words)
    # NOT_REACHED words are neither right nor wrong: leave them out of the denominator.
    total = sum(1 for w in words if w.status is not WordStatus.NOT_REACHED)
    correct = sum(
        1
        for w in words
        if w.status is not WordStatus.NOT_REACHED
        and (
            w.status not in ERROR_STATUSES
            or (excuse_accents and w.accent_excused and w.status is WordStatus.SUBSTITUTION)
        )
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
        words_reached=total,
        passage_words=passage_total,
    )


def _count_long_pauses(words: list[WordResult], long_pause_s: float) -> int:
    """Count gaps between consecutive timed words that meet or exceed the threshold."""
    timed = [w for w in words if w.start is not None and w.end is not None]
    return sum(
        1
        for prev, nxt in zip(timed, timed[1:])
        if (nxt.start - prev.end) >= long_pause_s
    )
