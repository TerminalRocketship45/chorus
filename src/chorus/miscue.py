"""Compare what a reader said against the passage they were given.

Uses difflib opcodes to align the two token sequences, then a second pass to
classify spoken words that align to no expected word. Reading teachers do not
count repetitions or self-corrections as errors.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from chorus.types import WordResult, WordStatus

_PUNCT = re.compile(r"[^\w']+")

# Minimum string similarity for an extra word to count as a failed attempt at the next word.
SELF_CORRECTION_MIN_SIMILARITY = 0.5


def normalize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into word tokens."""
    cleaned = _PUNCT.sub(" ", text.lower())
    return [t for t in cleaned.split() if t]


def detect_miscues(expected: list[str], heard: list[str]) -> list[WordResult]:
    """Classify each expected word against what was actually said.

    Returns exactly one WordResult per expected word, in passage order.
    """
    results: list[WordResult] = [
        WordResult(index=i, expected=w, heard=None, status=WordStatus.OMISSION)
        for i, w in enumerate(expected)
    ]
    # Extra tokens the reader produced that map to no expected word, keyed by
    # the expected index they were spoken before.
    extras: dict[int, list[str]] = {}

    matcher = SequenceMatcher(a=expected, b=heard, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                r = results[i1 + offset]
                r.heard = heard[j1 + offset]
                r.status = WordStatus.CORRECT
        elif tag == "replace":
            span = min(i2 - i1, j2 - j1)
            for offset in range(span):
                r = results[i1 + offset]
                r.heard = heard[j1 + offset]
                r.status = WordStatus.SUBSTITUTION
            # Expected words with no counterpart stay omissions.
            # Spoken words with no counterpart become extras.
            extras.setdefault(i2, []).extend(heard[j1 + span : j2])
        elif tag == "delete":
            pass  # already initialised as OMISSION
        elif tag == "insert":
            extras.setdefault(i1, []).extend(heard[j1:j2])

    _apply_extras(results, extras)
    return results


def _apply_extras(results: list[WordResult], extras: dict[int, list[str]]) -> None:
    """Classify spoken words that align to no expected word.

    For each extra token spoken before expected index `anchor`, the first
    matching rule applies:
      1. The token equals an adjacent expected word (anchor-1, anchor,
         anchor+1): a REPETITION of that word (or, if that word had been
         scored a substitution, a SELF_CORRECTION).
      2. The expected word at `anchor` was read CORRECT and the token is a
         different word but similar to it (ratio >=
         SELF_CORRECTION_MIN_SIMILARITY): the reader tried the wrong word
         first, then said the right one, so it becomes SELF_CORRECTION.
      3. Otherwise a genuine INSERTION, marked on the word at `anchor`
         (clamped to the last expected word).
    """
    for anchor, tokens in extras.items():
        for token in tokens:
            target = _nearest_expected(results, anchor, token)
            if target is not None:
                if target.status is WordStatus.SUBSTITUTION:
                    target.status = WordStatus.SELF_CORRECTION
                elif target.status is WordStatus.CORRECT:
                    target.status = WordStatus.REPETITION
                target.heard = token
                continue

            if anchor < len(results):
                nxt = results[anchor]
                if (
                    nxt.status is WordStatus.CORRECT
                    and token != nxt.expected
                    and SequenceMatcher(None, token, nxt.expected).ratio()
                    >= SELF_CORRECTION_MIN_SIMILARITY
                ):
                    nxt.status = WordStatus.SELF_CORRECTION
                    continue

            idx = min(anchor, len(results) - 1)
            if idx >= 0:
                results[idx].status = WordStatus.INSERTION


def _nearest_expected(
    results: list[WordResult], anchor: int, token: str
) -> WordResult | None:
    """Find an expected word adjacent to `anchor` that the token matches."""
    for idx in (anchor - 1, anchor, anchor + 1):
        if 0 <= idx < len(results) and results[idx].expected == token:
            return results[idx]
    return None
