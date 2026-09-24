"""Shared data contracts. Every pipeline stage speaks these types."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class WordStatus(StrEnum):
    """Running Record taxonomy, as used by reading teachers."""

    CORRECT = "correct"
    SUBSTITUTION = "substitution"
    OMISSION = "omission"
    INSERTION = "insertion"
    REPETITION = "repetition"
    SELF_CORRECTION = "self_correction"
    HESITATION = "hesitation"


#: Statuses that count against reading accuracy.
ERROR_STATUSES = frozenset(
    {WordStatus.SUBSTITUTION, WordStatus.OMISSION, WordStatus.INSERTION}
)


@dataclass
class WordResult:
    """One word of the expected passage, and what the reader did with it."""

    index: int
    expected: str
    heard: str | None
    status: WordStatus
    start: float | None = None
    end: float | None = None
    accent_excused: bool = False


@dataclass
class ReadingScore:
    accuracy: float
    wcpm: float
    total_words: int
    correct_words: int
    duration_s: float
    long_pauses: int


@dataclass
class Analysis:
    words: list[WordResult]
    score: ReadingScore
    accent_adjusted: ReadingScore | None
