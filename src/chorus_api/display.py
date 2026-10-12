"""Status -> display mapping (docs/api.md "Display status").

This is the single place the INSERTION caveat (see `chorus.types.WordStatus`)
is implemented for API clients: an INSERTION-status word may have been read
correctly (`heard == expected`), so it must never be rendered as a misread.
Clients colour by `display`, never by the raw `status`.
"""
from __future__ import annotations

from chorus.types import WordResult, WordStatus

#: `display` values, in the order docs/api.md lists them.
CORRECT = "correct"
ACCENT_OK = "accent_ok"
MISREAD = "misread"
SKIPPED = "skipped"
EXTRA_NEARBY = "extra_nearby"
REPEATED = "repeated"
SELF_CORRECTED = "self_corrected"

#: display values that the practice list is built from.
_PRACTICE_DISPLAYS = frozenset({MISREAD, SKIPPED})


def word_display(word: WordResult) -> str:
    """Map one WordResult's raw `status` (+ `accent_excused`) to its `display` value.

    Per docs/api.md:
      correct                                  -> "correct"
      substitution, accent_excused              -> "accent_ok"  (render as correct)
      substitution, not excused                 -> "misread"
      omission                                  -> "skipped"
      insertion (word itself may be correct!)   -> "extra_nearby", never "misread"
      repetition                                -> "repeated"
      self_correction                           -> "self_corrected"
      hesitation (engine never assigns this)    -> "correct" (defensive default;
                                                     docs: "clients may ignore it")
    """
    status = word.status
    if status is WordStatus.CORRECT:
        return CORRECT
    if status is WordStatus.SUBSTITUTION:
        return ACCENT_OK if word.accent_excused else MISREAD
    if status is WordStatus.OMISSION:
        return SKIPPED
    if status is WordStatus.INSERTION:
        return EXTRA_NEARBY
    if status is WordStatus.REPETITION:
        return REPEATED
    if status is WordStatus.SELF_CORRECTION:
        return SELF_CORRECTED
    if status is WordStatus.HESITATION:
        # Never assigned by the engine today; treat as not-an-error if it ever is.
        return CORRECT
    raise ValueError(f"unknown WordStatus: {status!r}")  # pragma: no cover


def practice_words(words: list[WordResult]) -> list[str]:
    """The practice list: `misread` and `skipped` words, de-duplicated, in passage order.

    `words` must already be in passage order (index-ascending), which is how
    `chorus.pipeline.analyze` returns them.
    """
    seen: set[str] = set()
    out: list[str] = []
    for w in words:
        if word_display(w) in _PRACTICE_DISPLAYS and w.expected not in seen:
            seen.add(w.expected)
            out.append(w.expected)
    return out


def accent_ok_count(words: list[WordResult]) -> int:
    """How many words display as `accent_ok` (teacher-view-only count)."""
    return sum(1 for w in words if word_display(w) == ACCENT_OK)
