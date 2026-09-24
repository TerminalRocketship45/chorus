"""First-language transfer rules.

A reader whose home language lacks an English phoneme will substitute the
nearest one available. That is an accent, not a reading error, and this module
decides which is which.

Rule sets are data, not code: adding a language means adding a JSON file.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from chorus.phonemes import to_phonemes

_DATA_DIR = Path(__file__).parent / "data"


@dataclass(frozen=True)
class RuleSet:
    language: str
    status: str
    substitutions: dict[str, tuple[str, ...]] = field(default_factory=dict)
    cluster_reduction: bool = False
    final_consonant_deletion: bool = False
    epenthesis: bool = False  # loaded from data but not yet matched by is_accent_variant
    sources: tuple[str, ...] = ()


def available_languages() -> list[str]:
    """Languages with a rule file present, sorted."""
    return sorted(p.stem for p in _DATA_DIR.glob("*.json"))


@lru_cache(maxsize=32)
def load_ruleset(language: str) -> RuleSet:
    """Load a rule set by language name. Raises KeyError if absent."""
    path = _DATA_DIR / f"{language}.json"
    if not path.exists():
        raise KeyError(f"No rule set for language: {language}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return RuleSet(
        language=raw["language"],
        status=raw["status"],
        substitutions={
            k: tuple(v) for k, v in raw.get("substitutions", {}).items()
        },
        cluster_reduction=raw.get("cluster_reduction", False),
        final_consonant_deletion=raw.get("final_consonant_deletion", False),
        epenthesis=raw.get("epenthesis", False),
        sources=tuple(raw.get("sources", [])),
    )


def is_accent_variant(expected_word: str, heard_word: str, rules: RuleSet) -> bool:
    """True if `heard_word` is `expected_word` filtered through this accent.

    Returns False for identical words: that is a correct read, and classifying
    it as accent would be misleading.
    """
    if expected_word == heard_word:
        return False
    expected = list(to_phonemes(expected_word))
    heard = list(to_phonemes(heard_word))
    if not expected or not heard:
        return False
    if _substitutions_explain(expected, heard, rules):
        return True
    if rules.final_consonant_deletion and _is_final_deletion(expected, heard):
        return True
    if rules.cluster_reduction and _is_cluster_reduction(expected, heard):
        return True
    return False


def _substitutions_explain(
    expected: list[str], heard: list[str], rules: RuleSet
) -> bool:
    """Every mismatch at the same position is a permitted substitution."""
    if len(expected) != len(heard):
        return False
    mismatches = 0
    for e, h in zip(expected, heard):
        if e == h:
            continue
        mismatches += 1
        if h not in rules.substitutions.get(e, ()):
            return False
    return mismatches > 0


def _is_final_deletion(expected: list[str], heard: list[str]) -> bool:
    """Reader dropped exactly the final consonant."""
    return (
        len(expected) == len(heard) + 1
        and expected[:-1] == heard
        and _is_consonant(expected[-1])
    )


def _is_cluster_reduction(expected: list[str], heard: list[str]) -> bool:
    """Heard form is the expected form with one consonant dropped from a run."""
    if len(expected) != len(heard) + 1:
        return False
    for i, p in enumerate(expected):
        if not _is_consonant(p):
            continue
        if expected[:i] + expected[i + 1 :] == heard and _in_cluster(expected, i):
            return True
    return False


_VOWEL_STARTS = ("A", "E", "I", "O", "U")


def _is_consonant(phoneme: str) -> bool:
    return not phoneme.startswith(_VOWEL_STARTS)


def _in_cluster(phonemes: list[str], i: int) -> bool:
    """True if the phoneme at i is adjacent to another consonant."""
    before = i > 0 and _is_consonant(phonemes[i - 1])
    after = i + 1 < len(phonemes) and _is_consonant(phonemes[i + 1])
    return before or after
