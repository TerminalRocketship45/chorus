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


_CANONICAL_INT = re.compile(r"0|[1-9][0-9]{0,2}")

_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _number_words(n: int) -> list[str]:
    """English cardinal words for 0 <= n <= 999, no "and" ("101" -> one hundred one)."""
    if n < 20:
        return [_ONES[n]]
    if n < 100:
        tens, ones = divmod(n, 10)
        return [_TENS[tens]] + ([_ONES[ones]] if ones else [])
    hundreds, rest = divmod(n, 100)
    words = [_ONES[hundreds], "hundred"]
    if rest:
        words += _number_words(rest)
    return words


def _contains_run(tokens: list[str], run: list[str]) -> bool:
    n = len(run)
    return any(tokens[i : i + n] == run for i in range(len(tokens) - n + 1))


def normalize(text: str, digit_context: list[str] | None = None) -> list[str]:
    """Lowercase, strip punctuation, split into word tokens.

    A token that is a canonical integer from 0 to 999 (no leading zeros except
    the single token "0") becomes its English cardinal words as separate tokens
    ("4" -> "four", "21" -> "twenty", "one", "101" -> "one", "hundred", "one").
    Both the expected passage and the ASR transcript pass through this
    function, so both land in the same space: a spoken number word and
    Whisper's digit rendering of it now match. Any other digit-bearing token
    ("2599", "1st", "007") is left unchanged. Limitation: decimals and
    thousands separators are split by the punctuation rule first, so "3.5" is
    read as "three", "five" and "1,000" as "one", "000" (each part mapped
    separately, so "000" stays unchanged).

    `digit_context` (opt-in, for the transcript side): Whisper writes a run of
    spoken digits ("four nine five") as one number ("495"), which is ambiguous
    between "four hundred ninety five" and digit-by-digit. When the expected
    tokens are given and the digit-by-digit reading appears in them but the
    cardinal reading does not, the digit-by-digit reading is used. If both or
    neither match, the default cardinal reading (or unchanged token) stays.
    """
    cleaned = _PUNCT.sub(" ", text.lower())
    out: list[str] = []
    for t in cleaned.split():
        if digit_context is not None and t.isascii() and t.isdigit() and len(t) > 1:
            digits = [_ONES[int(c)] for c in t]
            cardinal = (
                _number_words(int(t)) if _CANONICAL_INT.fullmatch(t) else None
            )
            if _contains_run(digit_context, digits) and not (
                cardinal and _contains_run(digit_context, cardinal)
            ):
                out.extend(digits)
                continue
        if _CANONICAL_INT.fullmatch(t):
            out.extend(_number_words(int(t)))
        else:
            out.append(t)
    return out


def detect_miscues(
    expected: list[str], heard: list[str], same_sound: bool = False
) -> list[WordResult]:
    """Classify each expected word against what was actually said.

    Returns exactly one WordResult per expected word, in passage order.

    With ``same_sound=True`` a SUBSTITUTION whose heard word has an identical
    CMU pronunciation to the expected word (two/too, their/there) is CORRECT:
    the recogniser chose a spelling, the reader said the right sound. `heard`
    keeps the recogniser's spelling. Off by default.
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

    if same_sound:
        from chorus.phonemes import same_sound as _same_sound

        for r in results:
            if (
                r.status is WordStatus.SUBSTITUTION
                and r.heard is not None
                and _same_sound(r.expected, r.heard)
            ):
                r.status = WordStatus.CORRECT

    _apply_extras(results, extras)
    return results


def _apply_extras(results: list[WordResult], extras: dict[int, list[str]]) -> None:
    """Classify spoken words that align to no expected word.

    This pass never modifies `heard`: it already holds the reader's first
    attempt or the matched token, and OMISSION results must keep heard=None.

    For each extra token spoken before expected index `anchor`, the first
    matching rule applies:
      1. The token equals an adjacent expected word (anchor-1, anchor,
         anchor+1): a CORRECT target becomes REPETITION and a SUBSTITUTION
         target becomes SELF_CORRECTION. A target in any other status is
         left untouched.
      2. The expected word at `anchor` is CORRECT or already SELF_CORRECTION
         and the token is a different word but similar to it (ratio >=
         SELF_CORRECTION_MIN_SIMILARITY): the reader tried a wrong word
         first, then said the right one, so it is SELF_CORRECTION (repeated
         wrong attempts stay SELF_CORRECTION).
      3. Otherwise a genuine INSERTION on the word at `anchor` (clamped to
         the last expected word), written only if that word is CORRECT or
         already INSERTION. It never overwrites SUBSTITUTION, OMISSION,
         REPETITION or SELF_CORRECTION.

    With one status per expected word, the number of extra words is not
    represented, and an insertion next to an already-flagged word is absorbed
    by that word's existing status.
    """
    for anchor, tokens in extras.items():
        for token in tokens:
            target = _nearest_expected(results, anchor, token)
            if target is not None:
                if target.status is WordStatus.SUBSTITUTION:
                    target.status = WordStatus.SELF_CORRECTION
                elif target.status is WordStatus.CORRECT:
                    target.status = WordStatus.REPETITION
                continue

            if anchor < len(results):
                nxt = results[anchor]
                if (
                    nxt.status in (WordStatus.CORRECT, WordStatus.SELF_CORRECTION)
                    and token != nxt.expected
                    and SequenceMatcher(None, token, nxt.expected).ratio()
                    >= SELF_CORRECTION_MIN_SIMILARITY
                ):
                    nxt.status = WordStatus.SELF_CORRECTION
                    continue

            idx = min(anchor, len(results) - 1)
            if idx >= 0 and results[idx].status in (
                WordStatus.CORRECT,
                WordStatus.INSERTION,
            ):
                results[idx].status = WordStatus.INSERTION


def _nearest_expected(
    results: list[WordResult], anchor: int, token: str
) -> WordResult | None:
    """Find an expected word adjacent to `anchor` that the token matches."""
    for idx in (anchor - 1, anchor, anchor + 1):
        if 0 <= idx < len(results) and results[idx].expected == token:
            return results[idx]
    return None
