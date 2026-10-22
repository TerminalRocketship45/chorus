"""Shared data contracts. Every pipeline stage speaks these types."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class WordStatus(StrEnum):
    """Running Record taxonomy, as used by reading teachers.

    There is one status per EXPECTED word. INSERTION caveat: an insertion (an
    extra word the reader added) is recorded on an adjacent expected word only
    when that word was read correctly, so a word with status INSERTION can be
    one the reader read correctly (heard == expected). Render it as "extra word
    added nearby", never as a misread word. The number of extra words is not
    represented.
    """

    CORRECT = "correct"
    SUBSTITUTION = "substitution"
    OMISSION = "omission"
    INSERTION = "insertion"
    REPETITION = "repetition"
    SELF_CORRECTION = "self_correction"
    HESITATION = "hesitation"


#: Statuses that count against reading accuracy.
#: INSERTION caveat (see WordStatus): a word with this status may have been
#: read correctly (heard == expected) with an extra word added nearby, so a UI
#: colouring words by status must show it as "extra word added nearby", not as
#: a misread. Accent-excused words (WordResult.accent_excused) must be
#: rendered as correct.
ERROR_STATUSES = frozenset(
    {WordStatus.SUBSTITUTION, WordStatus.OMISSION, WordStatus.INSERTION}
)


@dataclass
class WordResult:
    """One word of the expected passage, and what the reader did with it.

    `status` is the raw classification. INSERTION may sit on a word that was
    read correctly (`heard == expected`): it means "extra word added nearby",
    and how many were added is not represented. A word with `accent_excused`
    True keeps its SUBSTITUTION status but must be rendered as correct.
    """

    index: int
    expected: str
    heard: str | None
    status: WordStatus
    start: float | None = None
    end: float | None = None
    accent_excused: bool = False


@dataclass
class ReadingScore:
    """Scores for one read-aloud.

    accuracy is a FRACTION from 0 to 1 (not a percentage); wcpm is words per
    minute; duration_s is seconds of the WHOLE recording (leading and trailing
    silence included); long_pauses is a count of gaps at or above the pause
    threshold between consecutive TIMED words.
    """

    accuracy: float
    wcpm: float
    total_words: int
    correct_words: int
    duration_s: float
    long_pauses: int


@dataclass
class Analysis:
    """Result of analysing one read-aloud.

    `score` is the raw score; `accent_adjusted` is present only when a home
    language was given. Units are those of ReadingScore: accuracy is a
    fraction 0-1, wcpm is words per minute, duration_s is seconds of the whole
    recording, long_pauses is a count.
    """

    words: list[WordResult]
    score: ReadingScore
    accent_adjusted: ReadingScore | None
    #: The recogniser's raw text (after any hallucination filter), for display.
    transcript: str = ""
    #: Segments the hallucination filter removed (0 unless that option was on).
    dropped_segments: int = 0
