# Chorus — Analysis Engine Implementation Plan (Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested, CPU-runnable analysis engine that takes a child's read-aloud audio plus the expected passage text plus their first language, and returns word-by-word reading scores in which documented L1 accent features are not counted as reading errors.

**Architecture:** A linear pipeline of pure, independently testable stages. Audio goes to ASR to get what was actually said, and to forced alignment against the expected text to get word timings. An edit-distance aligner compares heard against expected to classify each word into the Running Record taxonomy. A scorer computes accuracy, WCPM, and pacing. Finally the L1 filter reclassifies deviations that match documented phonological transfer patterns for the reader's home language from "error" to "accent". Every stage below the ASR boundary is pure Python over plain data structures, so the whole thing is testable without a GPU or audio hardware.

**Tech Stack:** Python 3.12, pytest, faster-whisper (CTranslate2, CPU), torchaudio forced alignment, g2p_en for grapheme-to-phoneme, numpy. No GPU required for any task in this plan.

**Spec:** `docs/superpowers/specs/2026-09-23-reading-fluency-coach-design.md`

## Global Constraints

- **Deadline:** Monday, October 26, 2026, 12:00 PM EDT. This plan must complete by Oct 13 to leave room for Phase 2.
- **App name:** `Chorus`. Python package is `chorus`.
- **Hardware:** Development machine is CPU-only in practice — NVIDIA MX550 with 2GB VRAM, and PyTorch installed is the `+cpu` build. **No task in this plan may require a GPU.** Anything needing one is deferred to Phase 2 and must be isolated in `eval/notebooks/`.
- **Python:** 3.12.7 (Anaconda at `C:/Users/rohan/anaconda3FINAL/python`).
- **Whisper model:** `base.en` for tests (fast), `small.en` for real runs. Never `medium` — it will not fit.
- **Audio format:** All internal audio is mono 16 kHz float32. Convert at the boundary, never inside a stage.
- **Terminology (from spec §9), used exactly:** *validated* = measured against expert labels (Mandarin only); *shipped* = active in v1 (Mandarin, Somali, Spanish); *drafted* = encoded but not shipped (Hmong, Karen).
- **No clinical claims.** No function, comment, docstring, or output string may describe a reader as having a disorder, deficit, or impairment.
- **Never tell a reader their accent is wrong.** Accent-classified words render as correct.
- **Commit after every task.** Conventional commit prefixes (`feat:`, `test:`, `fix:`, `chore:`).

---

## File Structure

```
KasRep/
├── requirements.txt              # pinned deps
├── pytest.ini                    # test config
├── src/chorus/
│   ├── __init__.py
│   ├── types.py                  # shared dataclasses — every stage speaks these
│   ├── phonemes.py               # grapheme-to-phoneme, ARPAbet normalisation
│   ├── miscue.py                 # edit-distance alignment → word statuses
│   ├── scoring.py                # accuracy, WCPM, pacing
│   ├── asr.py                    # faster-whisper wrapper
│   ├── align.py                  # torchaudio forced alignment
│   ├── pipeline.py               # wires the stages into analyze()
│   └── l1/
│       ├── __init__.py
│       ├── engine.py             # rule matcher
│       └── data/
│           ├── mandarin.json     # validated
│           ├── somali.json       # shipped
│           └── spanish.json      # shipped
├── tests/
│   ├── conftest.py               # shared fixtures, synthetic audio
│   ├── test_phonemes.py
│   ├── test_miscue.py
│   ├── test_scoring.py
│   ├── test_l1_engine.py
│   ├── test_l1_data.py
│   ├── test_asr.py
│   ├── test_align.py
│   └── test_pipeline.py
└── eval/
    ├── fetch_speechocean.py      # download + verify corpus
    └── evaluate_l1_filter.py     # the headline metrics
```

**Responsibility boundaries.** `types.py` is the contract every other module imports; nothing else defines cross-stage data shapes. `miscue.py`, `scoring.py`, and `l1/engine.py` are pure — no I/O, no models, no audio — which is why they carry the most tests. `asr.py` and `align.py` are thin adapters isolating the two heavy third-party dependencies so they can be swapped or mocked. `pipeline.py` contains no logic of its own, only wiring.

---

### Task 1: Project scaffold and dependencies

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `src/chorus/__init__.py`, `tests/__init__.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing
- Produces: importable package `chorus` with `chorus.__version__` (str)

- [ ] **Step 1: Write the failing test**

Create `tests/test_smoke.py`:

```python
def test_package_imports():
    import chorus
    assert isinstance(chorus.__version__, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'chorus'`

- [ ] **Step 3: Create the package and config**

Create `src/chorus/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `tests/__init__.py` as an empty file.

Create `pytest.ini`:

```ini
[pytest]
pythonpath = src
testpaths = tests
addopts = -q
```

Create `requirements.txt`:

```
faster-whisper==1.1.1
torch==2.7.1
torchaudio==2.7.1
g2p-en==2.1.0
soundfile==0.12.1
librosa==0.10.2.post1
numpy==1.26.4
pytest==8.3.4
```

- [ ] **Step 4: Install dependencies**

Run: `python -m pip install -r requirements.txt`
Expected: completes without error. `torch` is already present as `2.7.1+cpu`; pip will keep it.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini src/chorus/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold chorus package and test harness"
```

---

### Task 2: Shared types

**Files:**
- Create: `src/chorus/types.py`
- Test: `tests/test_types.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `WordStatus` — str enum with members `CORRECT`, `SUBSTITUTION`, `OMISSION`, `INSERTION`, `REPETITION`, `SELF_CORRECTION`, `HESITATION`
  - `WordResult(index: int, expected: str, heard: str | None, status: WordStatus, start: float | None = None, end: float | None = None, accent_excused: bool = False)`
  - `ReadingScore(accuracy: float, wcpm: float, total_words: int, correct_words: int, duration_s: float, long_pauses: int)`
  - `Analysis(words: list[WordResult], score: ReadingScore, accent_adjusted: ReadingScore | None)`

- [ ] **Step 1: Write the failing test**

Create `tests/test_types.py`:

```python
from chorus.types import WordStatus, WordResult, ReadingScore, Analysis


def test_word_status_values():
    assert WordStatus.CORRECT == "correct"
    assert WordStatus.SELF_CORRECTION == "self_correction"


def test_word_result_defaults():
    w = WordResult(index=0, expected="cat", heard="cat", status=WordStatus.CORRECT)
    assert w.start is None
    assert w.accent_excused is False


def test_analysis_holds_words_and_score():
    score = ReadingScore(
        accuracy=1.0, wcpm=60.0, total_words=1,
        correct_words=1, duration_s=1.0, long_pauses=0,
    )
    a = Analysis(words=[], score=score, accent_adjusted=None)
    assert a.score.wcpm == 60.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'chorus.types'`

- [ ] **Step 3: Write the implementation**

Create `src/chorus/types.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_types.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/chorus/types.py tests/test_types.py
git commit -m "feat: shared pipeline data types"
```

---

### Task 3: Miscue detection

This is the heart of the engine and needs no ML, so it gets the heaviest test coverage.

**Files:**
- Create: `src/chorus/miscue.py`
- Test: `tests/test_miscue.py`

**Interfaces:**
- Consumes: `chorus.types.WordResult`, `chorus.types.WordStatus`
- Produces:
  - `normalize(text: str) -> list[str]` — lowercases, strips punctuation, splits on whitespace
  - `detect_miscues(expected: list[str], heard: list[str]) -> list[WordResult]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_miscue.py`:

```python
from chorus.miscue import normalize, detect_miscues
from chorus.types import WordStatus


def statuses(expected, heard):
    return [w.status for w in detect_miscues(normalize(expected), normalize(heard))]


def test_normalize_strips_punctuation_and_case():
    assert normalize("The cat, sat!") == ["the", "cat", "sat"]


def test_perfect_read_is_all_correct():
    assert statuses("the cat sat", "the cat sat") == [WordStatus.CORRECT] * 3


def test_substitution():
    assert statuses("the cat sat", "the cot sat") == [
        WordStatus.CORRECT, WordStatus.SUBSTITUTION, WordStatus.CORRECT,
    ]


def test_omission():
    assert statuses("the cat sat", "the sat") == [
        WordStatus.CORRECT, WordStatus.OMISSION, WordStatus.CORRECT,
    ]


def test_repetition_is_not_an_error():
    # Reader says "cat" twice. Second is a repetition, not an insertion.
    out = detect_miscues(normalize("the cat sat"), normalize("the cat cat sat"))
    assert [w.status for w in out] == [
        WordStatus.CORRECT, WordStatus.REPETITION, WordStatus.CORRECT,
    ]


def test_self_correction_is_not_an_error():
    # Reader says the wrong word, then immediately the right one.
    out = detect_miscues(normalize("the cat sat"), normalize("the cot cat sat"))
    assert [w.status for w in out] == [
        WordStatus.CORRECT, WordStatus.SELF_CORRECTION, WordStatus.CORRECT,
    ]


def test_heard_text_is_recorded_for_substitutions():
    out = detect_miscues(normalize("the cat"), normalize("the cot"))
    assert out[1].heard == "cot"


def test_omission_has_no_heard_text():
    out = detect_miscues(normalize("the cat sat"), normalize("the sat"))
    assert out[1].heard is None


def test_every_expected_word_appears_once():
    out = detect_miscues(normalize("a b c d e"), normalize("a x c e"))
    assert [w.expected for w in out] == ["a", "b", "c", "d", "e"]
    assert [w.index for w in out] == [0, 1, 2, 3, 4]


def test_empty_read_is_all_omissions():
    assert statuses("the cat sat", "") == [WordStatus.OMISSION] * 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_miscue.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'chorus.miscue'`

- [ ] **Step 3: Write the implementation**

Create `src/chorus/miscue.py`:

```python
"""Compare what a reader said against the passage they were given.

Uses difflib opcodes to align the two token sequences, then a second pass to
recognise repetitions and self-corrections, which reading teachers do not
count as errors.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from chorus.types import WordResult, WordStatus

_PUNCT = re.compile(r"[^\w']+")


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
    """Reinterpret unmatched spoken words as repetitions or self-corrections.

    An extra token spoken next to expected word W is:
      - a REPETITION if it equals W (the reader said it twice), or
      - a SELF_CORRECTION if W was scored a substitution and the extra token
        equals W (the reader got it wrong, then fixed it).
    Anything else is a genuine INSERTION.
    """
    for anchor, tokens in extras.items():
        for token in tokens:
            target = _nearest_expected(results, anchor, token)
            if target is None:
                idx = min(anchor, len(results) - 1)
                if idx >= 0:
                    results[idx].status = WordStatus.INSERTION
                continue
            if target.status is WordStatus.SUBSTITUTION:
                target.status = WordStatus.SELF_CORRECTION
            elif target.status is WordStatus.CORRECT:
                target.status = WordStatus.REPETITION
            target.heard = token


def _nearest_expected(
    results: list[WordResult], anchor: int, token: str
) -> WordResult | None:
    """Find an expected word adjacent to `anchor` that the token matches."""
    for idx in (anchor - 1, anchor, anchor + 1):
        if 0 <= idx < len(results) and results[idx].expected == token:
            return results[idx]
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_miscue.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add src/chorus/miscue.py tests/test_miscue.py
git commit -m "feat: miscue detection with repetition and self-correction handling"
```

---

### Task 4: Scoring

**Files:**
- Create: `src/chorus/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `chorus.types.WordResult`, `WordStatus`, `ERROR_STATUSES`, `ReadingScore`
- Produces:
  - `score_reading(words: list[WordResult], duration_s: float, long_pause_s: float = 1.0) -> ReadingScore`
  - `score_with_accent_excused(words: list[WordResult], duration_s: float, long_pause_s: float = 1.0) -> ReadingScore` — same, but words with `accent_excused=True` count as correct

- [ ] **Step 1: Write the failing test**

Create `tests/test_scoring.py`:

```python
import pytest

from chorus.scoring import score_reading, score_with_accent_excused
from chorus.types import WordResult, WordStatus


def w(i, status, start=None, end=None, excused=False):
    return WordResult(
        index=i, expected=f"w{i}", heard=f"w{i}", status=status,
        start=start, end=end, accent_excused=excused,
    )


def test_perfect_read_scores_one():
    words = [w(i, WordStatus.CORRECT) for i in range(10)]
    s = score_reading(words, duration_s=60.0)
    assert s.accuracy == 1.0
    assert s.wcpm == 10.0
    assert s.correct_words == 10


def test_errors_reduce_accuracy():
    words = [w(0, WordStatus.CORRECT), w(1, WordStatus.SUBSTITUTION)]
    s = score_reading(words, duration_s=60.0)
    assert s.accuracy == 0.5
    assert s.wcpm == 1.0


def test_repetition_and_self_correction_are_not_errors():
    words = [
        w(0, WordStatus.CORRECT),
        w(1, WordStatus.REPETITION),
        w(2, WordStatus.SELF_CORRECTION),
    ]
    s = score_reading(words, duration_s=60.0)
    assert s.accuracy == 1.0
    assert s.correct_words == 3


def test_wcpm_scales_with_duration():
    words = [w(i, WordStatus.CORRECT) for i in range(30)]
    assert score_reading(words, duration_s=30.0).wcpm == 60.0


def test_zero_duration_yields_zero_wcpm_not_crash():
    words = [w(0, WordStatus.CORRECT)]
    assert score_reading(words, duration_s=0.0).wcpm == 0.0


def test_empty_passage_yields_zero_accuracy_not_crash():
    s = score_reading([], duration_s=10.0)
    assert s.accuracy == 0.0
    assert s.total_words == 0


def test_long_pauses_counted_from_gaps():
    words = [
        w(0, WordStatus.CORRECT, start=0.0, end=0.5),
        w(1, WordStatus.CORRECT, start=2.0, end=2.5),  # 1.5s gap
        w(2, WordStatus.CORRECT, start=2.6, end=3.0),  # 0.1s gap
    ]
    assert score_reading(words, duration_s=3.0, long_pause_s=1.0).long_pauses == 1


def test_accent_excused_words_count_as_correct():
    words = [
        w(0, WordStatus.CORRECT),
        w(1, WordStatus.SUBSTITUTION, excused=True),
    ]
    raw = score_reading(words, duration_s=60.0)
    adjusted = score_with_accent_excused(words, duration_s=60.0)
    assert raw.accuracy == 0.5
    assert adjusted.accuracy == 1.0


def test_accent_excused_ignored_when_word_already_correct():
    words = [w(0, WordStatus.CORRECT, excused=True)]
    assert score_with_accent_excused(words, duration_s=60.0).accuracy == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'chorus.scoring'`

- [ ] **Step 3: Write the implementation**

Create `src/chorus/scoring.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scoring.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/chorus/scoring.py tests/test_scoring.py
git commit -m "feat: accuracy, WCPM and pacing scoring"
```

---

### Task 5: Grapheme-to-phoneme

**Files:**
- Create: `src/chorus/phonemes.py`
- Test: `tests/test_phonemes.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `to_phonemes(word: str) -> list[str]` — ARPAbet symbols with stress digits stripped, e.g. `"stop"` → `["S","T","AA","P"]`
  - `strip_stress(symbol: str) -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_phonemes.py`:

```python
from chorus.phonemes import strip_stress, to_phonemes


def test_strip_stress_removes_digits():
    assert strip_stress("AA1") == "AA"
    assert strip_stress("S") == "S"


def test_known_word_phonemes():
    assert list(to_phonemes("stop")) == ["S", "T", "AA", "P"]


def test_phonemes_are_stress_free():
    for p in to_phonemes("banana"):
        assert not any(c.isdigit() for c in p)


def test_case_insensitive():
    assert to_phonemes("Stop") == to_phonemes("stop")


def test_returns_a_tuple_so_it_can_be_cached():
    assert isinstance(to_phonemes("zzyzx"), tuple)


def test_empty_string_returns_empty():
    assert list(to_phonemes("")) == []
```

`to_phonemes` returns a tuple rather than a list so it can be safely
`lru_cache`d; passages repeat words heavily and G2P is the slowest pure-Python
step in the pipeline.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_phonemes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'chorus.phonemes'`

- [ ] **Step 3: Write the implementation**

Create `src/chorus/phonemes.py`:

```python
"""Grapheme-to-phoneme conversion.

Uses g2p_en (CMUdict plus a neural fallback for out-of-vocabulary words) and
emits stress-free ARPAbet, which is what the L1 rule sets are written against.
"""
from __future__ import annotations

from functools import lru_cache

_g2p = None


def _get_g2p():
    """Lazily construct the G2p object; it loads data files on first use."""
    global _g2p
    if _g2p is None:
        from g2p_en import G2p

        _g2p = G2p()
    return _g2p


def strip_stress(symbol: str) -> str:
    """Remove ARPAbet stress digits: 'AA1' -> 'AA'."""
    return "".join(c for c in symbol if not c.isdigit())


@lru_cache(maxsize=8192)
def to_phonemes(word: str) -> tuple[str, ...]:
    """Convert a single word to stress-free ARPAbet symbols.

    Cached because passages repeat words heavily. Returns a tuple so the
    cache stays safe; callers treat it as a sequence.
    """
    word = word.strip().lower()
    if not word:
        return ()
    raw = _get_g2p()(word)
    return tuple(
        strip_stress(p) for p in raw if p.isalnum() and not p.isspace()
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_phonemes.py -v`
Expected: PASS (6 tests). First run downloads g2p_en data and is slow.

- [ ] **Step 5: Commit**

```bash
git add src/chorus/phonemes.py tests/test_phonemes.py
git commit -m "feat: grapheme-to-phoneme conversion with ARPAbet output"
```

---

### Task 6: L1 rule engine

**Files:**
- Create: `src/chorus/l1/__init__.py`, `src/chorus/l1/engine.py`
- Test: `tests/test_l1_engine.py`

**Interfaces:**
- Consumes: `chorus.phonemes.to_phonemes`
- Produces:
  - `RuleSet` dataclass with fields `language: str`, `status: str`, `substitutions: dict[str, list[str]]`, `cluster_reduction: bool`, `final_consonant_deletion: bool`, `epenthesis: bool`, `sources: list[str]`
  - `load_ruleset(language: str) -> RuleSet`
  - `available_languages() -> list[str]`
  - `is_accent_variant(expected_word: str, heard_word: str, rules: RuleSet) -> bool`

- [ ] **Step 1: Write the failing test**

Create `tests/test_l1_engine.py`:

```python
import pytest

from chorus.l1.engine import (
    RuleSet, available_languages, is_accent_variant, load_ruleset,
)


@pytest.fixture
def somali():
    return load_ruleset("somali")


def test_shipped_languages_are_available():
    langs = available_languages()
    assert {"mandarin", "somali", "spanish"} <= set(langs)


def test_ruleset_has_sources():
    # Every rule set must cite where its patterns came from.
    for lang in available_languages():
        assert load_ruleset(lang).sources, f"{lang} has no sources"


def test_unknown_language_raises():
    with pytest.raises(KeyError):
        load_ruleset("klingon")


def test_identical_words_are_not_accent_variants(somali):
    # Same word is 'correct', not 'accent' — the caller handles that case.
    assert is_accent_variant("cat", "cat", somali) is False


def test_somali_p_to_b_substitution_is_accent(somali):
    # Somali lacks /p/; 'pat' realised as 'bat' is predictable transfer.
    assert is_accent_variant("pat", "bat", somali) is True


def test_somali_v_to_f_substitution_is_accent(somali):
    # Somali lacks /v/.
    assert is_accent_variant("van", "fan", somali) is True


def test_genuine_misread_is_not_accent(somali):
    # 'cat' read as 'dog' shares no phonology — a real error.
    assert is_accent_variant("cat", "dog", somali) is False


def test_unrelated_length_mismatch_is_not_accent(somali):
    assert is_accent_variant("cat", "elephant", somali) is False


def test_spanish_ruleset_loads_and_has_substitutions():
    rules = load_ruleset("spanish")
    assert isinstance(rules, RuleSet)
    assert rules.substitutions


def test_rule_status_is_a_known_value():
    for lang in available_languages():
        assert load_ruleset(lang).status in {"validated", "shipped", "drafted"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_l1_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'chorus.l1'`

- [ ] **Step 3: Write the implementation**

Create `src/chorus/l1/__init__.py` as an empty file.

Create `src/chorus/l1/engine.py`:

```python
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
    epenthesis: bool = False
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
```

- [ ] **Step 4: Run tests to verify they fail on missing data**

Run: `python -m pytest tests/test_l1_engine.py -v`
Expected: FAIL — the engine imports but no JSON rule files exist yet. This is the handoff to Task 7.

- [ ] **Step 5: Commit**

```bash
git add src/chorus/l1/__init__.py src/chorus/l1/engine.py tests/test_l1_engine.py
git commit -m "feat: L1 transfer rule engine"
```

---

### Task 7: L1 rule data — Mandarin, Somali, Spanish

Patterns are transcribed from the literature cited in spec §8. Every file carries its sources.

**Files:**
- Create: `src/chorus/l1/data/mandarin.json`, `somali.json`, `spanish.json`
- Test: `tests/test_l1_data.py` (plus Task 6's tests now pass)

**Interfaces:**
- Consumes: the `RuleSet` schema from Task 6
- Produces: three loadable rule sets

- [ ] **Step 1: Write the failing test**

Create `tests/test_l1_data.py`:

```python
import json
from pathlib import Path

import pytest

from chorus.l1.engine import load_ruleset

DATA = Path(__file__).parent.parent / "src" / "chorus" / "l1" / "data"
REQUIRED = {"language", "status", "sources"}


@pytest.mark.parametrize("lang", ["mandarin", "somali", "spanish"])
def test_file_has_required_fields(lang):
    raw = json.loads((DATA / f"{lang}.json").read_text(encoding="utf-8"))
    assert REQUIRED <= set(raw)


@pytest.mark.parametrize("lang", ["mandarin", "somali", "spanish"])
def test_substitution_targets_are_lists(lang):
    raw = json.loads((DATA / f"{lang}.json").read_text(encoding="utf-8"))
    for src, targets in raw.get("substitutions", {}).items():
        assert isinstance(targets, list), f"{lang}: {src} targets must be a list"
        assert targets, f"{lang}: {src} has no targets"


def test_mandarin_is_the_validated_language():
    # speechocean762 speakers are all Mandarin L1, so it is the only language
    # we can measure against expert labels.
    assert load_ruleset("mandarin").status == "validated"


def test_somali_and_spanish_are_shipped_not_validated():
    assert load_ruleset("somali").status == "shipped"
    assert load_ruleset("spanish").status == "shipped"


def test_somali_lacks_p_and_v():
    subs = load_ruleset("somali").substitutions
    assert "B" in subs["P"]
    assert "F" in subs["V"]


def test_somali_has_epenthesis_and_cluster_reduction():
    rules = load_ruleset("somali")
    assert rules.epenthesis is True
    assert rules.cluster_reduction is True


def test_mandarin_has_th_substitutions():
    subs = load_ruleset("mandarin").substitutions
    assert "TH" in subs
    assert "DH" in subs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_l1_data.py -v`
Expected: FAIL with `FileNotFoundError`

- [ ] **Step 3: Write the rule files**

Create `src/chorus/l1/data/somali.json`:

```json
{
  "language": "somali",
  "status": "shipped",
  "notes": "Somali lacks several English phonemes and disallows word-initial consonant clusters. Syllable structure is CV, CVC, V, rarely more than two consonants together.",
  "substitutions": {
    "P": ["B"],
    "V": ["F", "B"],
    "ZH": ["SH", "J"],
    "CH": ["SH"],
    "JH": ["J", "Y"],
    "NG": ["N"],
    "TH": ["T", "S"],
    "DH": ["D", "Z"],
    "R": ["L"]
  },
  "cluster_reduction": true,
  "final_consonant_deletion": false,
  "epenthesis": true,
  "sources": [
    "Somali phonology: inventory lacks /p/ /v/ /ʒ/ /tʃ/ /dʒ/ /ŋ/ /θ/ /ð/ /ɹ/",
    "Koffi (2011), Pronunciation of S-Clusters in Somali-Accented English, St. Cloud State University",
    "Somali syllable structure CV, CVC, V; word-initial clusters resolved by epenthesis ('stop' -> [sitop]/[istop])"
  ]
}
```

Create `src/chorus/l1/data/mandarin.json`:

```json
{
  "language": "mandarin",
  "status": "validated",
  "notes": "Validated against speechocean762, whose 250 non-native speakers are all Mandarin L1. Mandarin disallows most final consonants and lacks the English dental fricatives.",
  "substitutions": {
    "TH": ["S", "T", "F"],
    "DH": ["D", "Z"],
    "V": ["W", "F"],
    "Z": ["S"],
    "ZH": ["SH"],
    "R": ["L", "W"],
    "N": ["NG"],
    "NG": ["N"]
  },
  "cluster_reduction": true,
  "final_consonant_deletion": true,
  "epenthesis": true,
  "sources": [
    "Swan & Smith, Learner English: A Teacher's Guide to Interference and Other Problems, Cambridge — Chinese chapter",
    "speechocean762 (arXiv 2104.01378): 5000 utterances, 250 non-native Mandarin L1 speakers, half children, expert phoneme-level accuracy labels"
  ]
}
```

Create `src/chorus/l1/data/spanish.json`:

```json
{
  "language": "spanish",
  "status": "shipped",
  "notes": "Spanish lacks the English dental fricatives and several vowel contrasts, and disallows word-initial /s/+consonant clusters without a preceding vowel.",
  "substitutions": {
    "TH": ["T", "S"],
    "DH": ["D"],
    "V": ["B"],
    "Z": ["S"],
    "ZH": ["Y", "SH"],
    "JH": ["Y", "CH"],
    "IH": ["IY"],
    "AE": ["EH", "AA"],
    "UH": ["UW"]
  },
  "cluster_reduction": false,
  "final_consonant_deletion": false,
  "epenthesis": true,
  "sources": [
    "Swan & Smith, Learner English: A Teacher's Guide to Interference and Other Problems, Cambridge — Spanish chapter",
    "Problematic Phonemes for Spanish-speaking Learners of English (ERIC EJ1237446)"
  ]
}
```

- [ ] **Step 4: Run both L1 test files to verify they pass**

Run: `python -m pytest tests/test_l1_data.py tests/test_l1_engine.py -v`
Expected: PASS (all of Task 6 and Task 7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/chorus/l1/data tests/test_l1_data.py
git commit -m "feat: Mandarin, Somali and Spanish L1 rule sets with cited sources"
```

---

### Task 8: ASR adapter

**Files:**
- Create: `src/chorus/asr.py`, `tests/conftest.py`
- Test: `tests/test_asr.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `Transcript(text: str, duration_s: float)` dataclass
  - `transcribe(audio_path: str | Path, model_size: str = "base.en") -> Transcript`

- [ ] **Step 1: Write the failing test**

Create `tests/conftest.py`:

```python
"""Shared fixtures. Generates a real WAV so audio tests need no recording."""
import wave
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture(scope="session")
def silence_wav(tmp_path_factory) -> Path:
    """One second of near-silence at 16 kHz mono, as a real WAV file."""
    path = tmp_path_factory.mktemp("audio") / "silence.wav"
    samples = (np.random.default_rng(0).normal(0, 1e-4, 16000) * 32767).astype(
        np.int16
    )
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(samples.tobytes())
    return path
```

Create `tests/test_asr.py`:

```python
import pytest

from chorus.asr import Transcript, transcribe


def test_transcript_dataclass_fields():
    t = Transcript(text="hello", duration_s=1.0)
    assert t.text == "hello"
    assert t.duration_s == 1.0


@pytest.mark.slow
def test_transcribe_returns_transcript(silence_wav):
    result = transcribe(silence_wav, model_size="base.en")
    assert isinstance(result, Transcript)
    assert isinstance(result.text, str)
    assert result.duration_s > 0


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        transcribe(tmp_path / "nope.wav")
```

Add to `pytest.ini` under `[pytest]`:

```ini
markers =
    slow: downloads or runs a model; excluded by default with -m "not slow"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_asr.py -v -m "not slow"`
Expected: FAIL with `ModuleNotFoundError: No module named 'chorus.asr'`

- [ ] **Step 3: Write the implementation**

Create `src/chorus/asr.py`:

```python
"""Speech recognition adapter.

Isolates faster-whisper so the rest of the engine never imports it directly.
faster-whisper is chosen over openai-whisper because this project must run
inference on CPU; CTranslate2 is several times faster there.

Model sizing: base.en for tests, small.en for real runs. Never medium — it
will not fit the 2GB GPU and is slow on CPU.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass
class Transcript:
    text: str
    duration_s: float


@lru_cache(maxsize=2)
def _get_model(model_size: str):
    """Load and cache a Whisper model. int8 keeps CPU inference tractable."""
    from faster_whisper import WhisperModel

    return WhisperModel(model_size, device="cpu", compute_type="int8")


def transcribe(audio_path: str | Path, model_size: str = "base.en") -> Transcript:
    """Transcribe an audio file. Returns what was said, not what was expected."""
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    model = _get_model(model_size)
    segments, info = model.transcribe(str(path), language="en", beam_size=1)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return Transcript(text=text, duration_s=float(info.duration))
```

- [ ] **Step 4: Run fast tests to verify they pass**

Run: `python -m pytest tests/test_asr.py -v -m "not slow"`
Expected: PASS (2 tests; the model-loading test is skipped)

- [ ] **Step 5: Run the slow test once to confirm the model actually loads**

Run: `python -m pytest tests/test_asr.py -v -m slow`
Expected: PASS. First run downloads the model (~75MB) and takes a few minutes.

- [ ] **Step 6: Commit**

```bash
git add src/chorus/asr.py tests/conftest.py tests/test_asr.py pytest.ini
git commit -m "feat: faster-whisper ASR adapter for CPU inference"
```

---

### Task 9: Forced alignment

**Files:**
- Create: `src/chorus/align.py`
- Test: `tests/test_align.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `WordTiming(word: str, start: float, end: float, score: float)` dataclass
  - `align_words(audio_path: str | Path, expected_text: str) -> list[WordTiming]`

Uses `torchaudio.pipelines.MMS_FA`, which ships a CTC model and its own tokenizer and runs acceptably on CPU. Chosen over Montreal Forced Aligner because MFA requires a separate Kaldi-based install that is painful on Windows.

- [ ] **Step 1: Write the failing test**

Create `tests/test_align.py`:

```python
import pytest

from chorus.align import WordTiming, align_words


def test_word_timing_fields():
    t = WordTiming(word="cat", start=0.0, end=0.5, score=0.9)
    assert t.end > t.start


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        align_words(tmp_path / "nope.wav", "the cat sat")


def test_empty_text_returns_empty(silence_wav):
    assert align_words(silence_wav, "") == []


@pytest.mark.slow
def test_alignment_returns_one_timing_per_word(silence_wav):
    out = align_words(silence_wav, "the cat sat")
    assert len(out) == 3
    assert [t.word for t in out] == ["the", "cat", "sat"]


@pytest.mark.slow
def test_timings_are_monotonic(silence_wav):
    out = align_words(silence_wav, "the cat sat")
    for prev, nxt in zip(out, out[1:]):
        assert prev.start <= nxt.start
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_align.py -v -m "not slow"`
Expected: FAIL with `ModuleNotFoundError: No module named 'chorus.align'`

- [ ] **Step 3: Write the implementation**

Create `src/chorus/align.py`:

```python
"""Forced alignment of audio against the expected passage text.

This is deliberately separate from ASR. ASR answers "what did they say";
alignment answers "when did they say each expected word". Timings feed the
pacing metric, and the per-word confidence scores flag words the reader
struggled to produce even when the word itself was right.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

TARGET_SR = 16000


@dataclass
class WordTiming:
    word: str
    start: float
    end: float
    score: float


@lru_cache(maxsize=1)
def _get_bundle():
    """Load and cache the MMS forced-alignment bundle."""
    import torchaudio

    return torchaudio.pipelines.MMS_FA


def _load_audio(path: Path):
    """Load audio as mono 16 kHz float32, resampling if needed."""
    import torch
    import torchaudio

    waveform, sr = torchaudio.load(str(path))
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if sr != TARGET_SR:
        waveform = torchaudio.functional.resample(waveform, sr, TARGET_SR)
    return waveform.to(torch.float32)


def align_words(audio_path: str | Path, expected_text: str) -> list[WordTiming]:
    """Return one timing per whitespace-separated word in `expected_text`."""
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    words = expected_text.lower().split()
    if not words:
        return []

    import torch
    import torchaudio.functional as F

    bundle = _get_bundle()
    model = bundle.get_model()
    tokenizer = bundle.get_tokenizer()
    aligner = bundle.get_aligner()

    waveform = _load_audio(path)
    with torch.inference_mode():
        emission, _ = model(waveform)
        token_spans = aligner(emission[0], tokenizer(words))

    ratio = waveform.shape[1] / emission.shape[1] / TARGET_SR
    return [
        WordTiming(
            word=word,
            start=spans[0].start * ratio,
            end=spans[-1].end * ratio,
            score=sum(s.score for s in spans) / len(spans),
        )
        for word, spans in zip(words, token_spans)
    ]
```

- [ ] **Step 4: Run fast tests to verify they pass**

Run: `python -m pytest tests/test_align.py -v -m "not slow"`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the slow tests once to confirm alignment works end to end**

Run: `python -m pytest tests/test_align.py -v -m slow`
Expected: PASS. First run downloads the MMS_FA model.

If the aligner raises on the near-silent fixture (it may fail to find any
plausible alignment), record the real exception type and change
`test_alignment_returns_one_timing_per_word` to assert that a
`RuntimeError` is raised for unalignable audio, then add a real spoken WAV
under `tests/fixtures/` and re-point the slow tests at it. Do not weaken the
production code to make the fixture pass.

- [ ] **Step 6: Commit**

```bash
git add src/chorus/align.py tests/test_align.py
git commit -m "feat: forced alignment producing per-word timings"
```

---

### Task 10: Pipeline integration

**Files:**
- Create: `src/chorus/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `asr.transcribe`, `align.align_words`, `miscue.normalize`, `miscue.detect_miscues`, `scoring.score_reading`, `scoring.score_with_accent_excused`, `l1.engine.load_ruleset`, `l1.engine.is_accent_variant`
- Produces:
  - `analyze(audio_path, expected_text, language=None, model_size="base.en") -> Analysis`
  - `apply_l1_filter(words: list[WordResult], language: str) -> list[WordResult]` — pure, mutates nothing, returns new list with `accent_excused` set

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline.py`:

```python
import pytest

from chorus.pipeline import apply_l1_filter
from chorus.types import WordResult, WordStatus


def sub(index, expected, heard):
    return WordResult(
        index=index, expected=expected, heard=heard,
        status=WordStatus.SUBSTITUTION,
    )


def test_filter_excuses_predictable_somali_substitution():
    out = apply_l1_filter([sub(0, "pat", "bat")], "somali")
    assert out[0].accent_excused is True
    # The status is preserved; only the excusal flag changes.
    assert out[0].status == WordStatus.SUBSTITUTION


def test_filter_leaves_genuine_error_alone():
    out = apply_l1_filter([sub(0, "cat", "dog")], "somali")
    assert out[0].accent_excused is False


def test_filter_ignores_correct_words():
    w = WordResult(index=0, expected="cat", heard="cat", status=WordStatus.CORRECT)
    assert apply_l1_filter([w], "somali")[0].accent_excused is False


def test_filter_ignores_omissions_with_no_heard_text():
    w = WordResult(index=0, expected="cat", heard=None, status=WordStatus.OMISSION)
    assert apply_l1_filter([w], "somali")[0].accent_excused is False


def test_filter_does_not_mutate_input():
    original = sub(0, "pat", "bat")
    apply_l1_filter([original], "somali")
    assert original.accent_excused is False


def test_unknown_language_raises():
    with pytest.raises(KeyError):
        apply_l1_filter([sub(0, "pat", "bat")], "klingon")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'chorus.pipeline'`

- [ ] **Step 3: Write the implementation**

Create `src/chorus/pipeline.py`:

```python
"""Wiring only. Every piece of logic lives in the stage modules."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from chorus.align import align_words
from chorus.asr import transcribe
from chorus.l1.engine import is_accent_variant, load_ruleset
from chorus.miscue import detect_miscues, normalize
from chorus.scoring import score_reading, score_with_accent_excused
from chorus.types import Analysis, WordResult, WordStatus


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


def _attach_timings(words: list[WordResult], timings) -> list[WordResult]:
    """Copy alignment timings onto word results by position."""
    out = []
    for w in words:
        t = timings[w.index] if w.index < len(timings) else None
        out.append(
            replace(w, start=t.start, end=t.end) if t else replace(w)
        )
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

    timings = align_words(audio_path, " ".join(expected_tokens))
    words = _attach_timings(words, timings)

    raw = score_reading(words, duration_s=transcript.duration_s)
    adjusted = None
    if language:
        words = apply_l1_filter(words, language)
        adjusted = score_with_accent_excused(
            words, duration_s=transcript.duration_s
        )
    return Analysis(words=words, score=raw, accent_adjusted=adjusted)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the whole fast suite**

Run: `python -m pytest -v -m "not slow"`
Expected: PASS, no failures

- [ ] **Step 6: Commit**

```bash
git add src/chorus/pipeline.py tests/test_pipeline.py
git commit -m "feat: wire analysis pipeline with L1 accent filter"
```

---

### Task 11: speechocean762 fetcher

**Files:**
- Create: `eval/fetch_speechocean.py`
- Test: `tests/test_fetch_speechocean.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `CORPUS_URL` (str) and `DEFAULT_DEST` (Path)
  - `parse_scores(scores_json: dict) -> list[Utterance]` where `Utterance(uttid: str, text: str, accuracy: float, fluency: float, prosody: float, total: float, words: list[dict])`
  - `download(dest: Path = DEFAULT_DEST) -> Path`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fetch_speechocean.py`:

```python
from eval.fetch_speechocean import Utterance, parse_scores

SAMPLE = {
    "000010011": {
        "text": "MARK IS GOING TO SCHOOL",
        "accuracy": 8.0,
        "fluency": 9.0,
        "prosodic": 9.0,
        "total": 8.0,
        "words": [
            {
                "text": "MARK",
                "accuracy": 9.0,
                "stress": 10.0,
                "total": 9.0,
                "phones": ["M", "AA0", "R", "K"],
                "phones-accuracy": [2.0, 2.0, 1.0, 2.0],
            }
        ],
    }
}


def test_parse_returns_utterances():
    out = parse_scores(SAMPLE)
    assert len(out) == 1
    assert isinstance(out[0], Utterance)


def test_parse_reads_sentence_scores():
    u = parse_scores(SAMPLE)[0]
    assert u.uttid == "000010011"
    assert u.accuracy == 8.0
    assert u.prosody == 9.0


def test_parse_keeps_word_detail():
    u = parse_scores(SAMPLE)[0]
    assert u.words[0]["text"] == "MARK"
    assert u.words[0]["phones-accuracy"] == [2.0, 2.0, 1.0, 2.0]


def test_parse_handles_empty_input():
    assert parse_scores({}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fetch_speechocean.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'eval'`

- [ ] **Step 3: Write the implementation**

Create `eval/__init__.py` as an empty file.

Create `eval/fetch_speechocean.py`:

```python
"""Fetch and parse speechocean762.

5000 English utterances from 250 non-native speakers (all Mandarin L1, half
of them children), labelled by five experts at sentence, word and phoneme
level. Free for commercial and non-commercial use. This is the only labelled
non-native corpus available to us, which is why Mandarin is the sole
'validated' language in the spec.
"""
from __future__ import annotations

import json
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CORPUS_URL = "https://www.openslr.org/resources/101/speechocean762.tar.gz"
DEFAULT_DEST = Path(__file__).parent / "data" / "speechocean762"


@dataclass
class Utterance:
    uttid: str
    text: str
    accuracy: float
    fluency: float
    prosody: float
    total: float
    words: list[dict]


def parse_scores(scores_json: dict) -> list[Utterance]:
    """Convert the corpus scores.json structure into Utterance records."""
    return [
        Utterance(
            uttid=uttid,
            text=entry["text"],
            accuracy=float(entry["accuracy"]),
            fluency=float(entry["fluency"]),
            prosody=float(entry["prosodic"]),
            total=float(entry["total"]),
            words=entry.get("words", []),
        )
        for uttid, entry in scores_json.items()
    ]


def download(dest: Path = DEFAULT_DEST) -> Path:
    """Download and extract the corpus. Idempotent."""
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "speechocean762.tar.gz"
    if not (dest / "resource").exists():
        if not archive.exists():
            print(f"Downloading {CORPUS_URL} ...")
            urllib.request.urlretrieve(CORPUS_URL, archive)
        print("Extracting ...")
        with tarfile.open(archive) as tf:
            tf.extractall(dest, filter="data")
    return dest


def load_scores(dest: Path = DEFAULT_DEST) -> list[Utterance]:
    """Load the parsed score records from an already-downloaded corpus."""
    path = dest / "resource" / "scores.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run: python -m eval.fetch_speechocean"
        )
    return parse_scores(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    out = download()
    print(f"Corpus ready at {out}")
    print(f"Loaded {len(load_scores(out))} utterances")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_fetch_speechocean.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Download the corpus for real**

Run: `python -m eval.fetch_speechocean`
Expected: prints the corpus path and an utterance count near 5000.

If the archive layout differs from `resource/scores.json`, locate the real
path with `find eval/data -name "scores.json"` and correct `load_scores`.

- [ ] **Step 6: Commit**

```bash
git add eval/__init__.py eval/fetch_speechocean.py tests/test_fetch_speechocean.py
git commit -m "feat: speechocean762 fetcher and score parser"
```

Add `eval/data/` to `.gitignore` before committing — the corpus must not enter git.

---

### Task 12: L1 filter evaluation — the headline numbers

This task produces the figure that goes in the demonstration video.

**Files:**
- Create: `eval/evaluate_l1_filter.py`
- Test: `tests/test_evaluate_l1_filter.py`

**Interfaces:**
- Consumes: `eval.fetch_speechocean.Utterance`, `chorus.l1.engine`, `chorus.pipeline`
- Produces:
  - `WordRecord(expected: str, heard: str | None, expert_accuracy: float)`
  - `FilterMetrics(fp_before: int, fp_after: int, tp_before: int, tp_after: int)` with properties `fp_reduction: float` and `retention: float`
  - `evaluate(records: list[WordRecord], language: str) -> FilterMetrics`
  - `build_records(utterances, audio_root, limit) -> list[WordRecord]`

**Measurement design — read this before implementing.** The metric needs
three things per word: what the experts said, what our system said *before*
the filter, and what it said *after*. Expert labels alone cannot produce the
"before" column, because speechocean762 records how well each phoneme was
pronounced but not which phoneme the speaker actually produced. So the
system's opinion must come from actually running the pipeline over the corpus
audio.

Evaluation is therefore at **word** level, which is also the level our
pipeline genuinely operates at:

| | Expert says correct | Expert says mispronounced |
|---|---|---|
| System flags it | **false positive** | true positive |
| System lets it pass | true negative | false negative |

- `fp_reduction = (fp_before - fp_after) / fp_before` — how many wrong accusations the filter withdraws
- `retention = tp_after / tp_before` — how many real errors survive filtering

These must be reported together. A filter that excuses everything scores a
perfect `fp_reduction` and a `retention` of zero.

Ground truth threshold: speechocean762 scores each word 0–10 for accuracy.
A word scoring **≥ 8.0** is treated as expert-correct.

- [ ] **Step 1: Write the failing test**

Create `tests/test_evaluate_l1_filter.py`:

```python
from eval.evaluate_l1_filter import FilterMetrics, WordRecord, evaluate


def test_metrics_compute_ratios():
    m = FilterMetrics(fp_before=100, fp_after=40, tp_before=50, tp_after=48)
    assert m.fp_reduction == 0.6
    assert m.retention == 0.96


def test_metrics_handle_zero_denominators():
    m = FilterMetrics(0, 0, 0, 0)
    assert m.fp_reduction == 0.0
    assert m.retention == 0.0


def test_correct_read_is_never_flagged():
    # Heard matches expected, expert agrees. Not a false positive either way.
    m = evaluate([WordRecord("think", "think", 10.0)], "mandarin")
    assert m.fp_before == 0
    assert m.tp_before == 0


def test_accent_substitution_on_expert_correct_word_is_a_false_positive():
    # Experts scored it correct; the baseline flags it because ASR heard
    # 'sink'. Mandarin lacks /TH/, so the filter should withdraw the flag.
    m = evaluate([WordRecord("think", "sink", 9.0)], "mandarin")
    assert m.fp_before == 1
    assert m.fp_after == 0
    assert m.fp_reduction == 1.0


def test_genuine_error_survives_the_filter():
    # Experts scored it badly and 'dog' is not a phonological variant of
    # 'cat' in Mandarin, so it must stay flagged.
    m = evaluate([WordRecord("cat", "dog", 2.0)], "mandarin")
    assert m.tp_before == 1
    assert m.tp_after == 1
    assert m.retention == 1.0


def test_filter_wrongly_excusing_a_real_error_lowers_retention():
    # Experts scored 'think' badly, but the filter excuses TH->S anyway.
    # This is the failure mode retention exists to expose.
    m = evaluate([WordRecord("think", "sink", 1.0)], "mandarin")
    assert m.tp_before == 1
    assert m.tp_after == 0
    assert m.retention == 0.0


def test_omitted_word_is_flagged_and_never_excused():
    m = evaluate([WordRecord("think", None, 1.0)], "mandarin")
    assert m.tp_before == 1
    assert m.tp_after == 1


def test_evaluate_handles_empty_input():
    assert evaluate([], "mandarin").fp_before == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_evaluate_l1_filter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'eval.evaluate_l1_filter'`

- [ ] **Step 3: Write the implementation**

Create `eval/evaluate_l1_filter.py`:

```python
"""Measure what the L1 filter buys, against expert word-level labels.

Two numbers, which must always be reported together:

  fp_reduction — of the words the experts judged correct but the unfiltered
                 baseline flagged, the share the filter withdraws.
  retention    — of the words the experts judged mispronounced, the share
                 still flagged after filtering. The guardrail: a filter that
                 excuses everything scores fp_reduction 1.0 and retention 0.0.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chorus.l1.engine import is_accent_variant, load_ruleset
from chorus.miscue import normalize

#: speechocean762 scores each word 0-10. At or above this, experts judged it correct.
EXPERT_CORRECT = 8.0


@dataclass
class WordRecord:
    """One expected word, what our ASR heard, and what the experts scored it."""

    expected: str
    heard: str | None
    expert_accuracy: float


@dataclass
class FilterMetrics:
    fp_before: int
    fp_after: int
    tp_before: int
    tp_after: int

    @property
    def fp_reduction(self) -> float:
        if not self.fp_before:
            return 0.0
        return (self.fp_before - self.fp_after) / self.fp_before

    @property
    def retention(self) -> float:
        if not self.tp_before:
            return 0.0
        return self.tp_after / self.tp_before


def evaluate(records: list[WordRecord], language: str) -> FilterMetrics:
    """Build the before/after confusion counts for one language."""
    rules = load_ruleset(language)
    fp_before = fp_after = tp_before = tp_after = 0

    for r in records:
        expert_ok = r.expert_accuracy >= EXPERT_CORRECT
        # The unfiltered baseline flags any word that was not heard verbatim.
        flagged_before = r.heard != r.expected
        # The filter can only ever withdraw a flag, never add one. An omitted
        # word (heard is None) is never excusable: silence is not an accent.
        excused = (
            flagged_before
            and r.heard is not None
            and is_accent_variant(r.expected, r.heard, rules)
        )
        flagged_after = flagged_before and not excused

        if expert_ok:
            fp_before += int(flagged_before)
            fp_after += int(flagged_after)
        else:
            tp_before += int(flagged_before)
            tp_after += int(flagged_after)

    return FilterMetrics(fp_before, fp_after, tp_before, tp_after)


def build_records(utterances, audio_root: Path, limit: int = 500):
    """Run ASR over corpus audio to get the system's opinion per word.

    This is the slow step. `limit` keeps a CPU run to roughly an hour; raise
    it on the GPU machine for the final numbers.
    """
    from chorus.asr import transcribe
    from chorus.miscue import detect_miscues

    records: list[WordRecord] = []
    for u in utterances[:limit]:
        wav = audio_root / f"{u.uttid}.wav"
        if not wav.exists():
            continue
        heard_tokens = normalize(transcribe(wav).text)
        expected_tokens = normalize(u.text)
        results = detect_miscues(expected_tokens, heard_tokens)
        for result, word in zip(results, u.words):
            records.append(
                WordRecord(
                    expected=result.expected,
                    heard=result.heard,
                    expert_accuracy=float(word.get("accuracy", 0.0)),
                )
            )
    return records


def main() -> None:
    import json

    from eval.fetch_speechocean import DEFAULT_DEST, load_scores

    utterances = load_scores()
    audio_root = DEFAULT_DEST / "WAVE"
    records = build_records(utterances, audio_root)
    m = evaluate(records, "mandarin")

    print(f"words scored            : {len(records)}")
    print(f"false positives before  : {m.fp_before}")
    print(f"false positives after   : {m.fp_after}")
    print(f"true positives before   : {m.tp_before}")
    print(f"true positives after    : {m.tp_after}")
    print(f"false-positive reduction: {m.fp_reduction:.1%}")
    print(f"genuine-error retention : {m.retention:.1%}")

    Path("eval/results.json").write_text(
        json.dumps(
            {
                "words": len(records),
                "fp_before": m.fp_before,
                "fp_after": m.fp_after,
                "tp_before": m.tp_before,
                "tp_after": m.tp_after,
                "fp_reduction": m.fp_reduction,
                "retention": m.retention,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_evaluate_l1_filter.py -v`
Expected: PASS (8 tests). These are pure and fast — no audio, no models.

- [ ] **Step 5: Run the real evaluation**

Run: `python -m eval.evaluate_l1_filter`

This transcribes 500 corpus utterances on CPU and takes roughly an hour.
Confirm `eval/data/speechocean762/WAVE/` exists first; if the audio lives at
a different path, correct `audio_root` in `main()` rather than guessing.

Expected: prints all six counts plus both percentages, and writes
`eval/results.json`.

**Record the output in spec §9**, replacing the `measured` placeholders.
These are the numbers the demonstration video quotes.

Read the two numbers together before accepting them:

| Outcome | Meaning | Action |
|---|---|---|
| High `fp_reduction`, high `retention` | The filter works | Proceed |
| High `fp_reduction`, low `retention` | Rules too permissive — excusing real errors | Tighten `substitutions` in `mandarin.json`, re-run |
| Low `fp_reduction` | Rules too narrow, or ASR is not producing the substitutions the rules predict | Inspect a sample of `fp_before` words before touching rules |

Do not report `fp_reduction` on its own in any submission material.

- [ ] **Step 6: Commit**

```bash
git add eval/evaluate_l1_filter.py tests/test_evaluate_l1_filter.py
git commit -m "feat: L1 filter evaluation against speechocean762 expert labels"
```

---

## Definition of done for Phase 1

- `python -m pytest -m "not slow"` passes with no failures
- `python -m pytest -m slow` passes (model downloads complete)
- `python -m eval.evaluate_l1_filter` prints real percentages
- Those percentages are written into spec §9, replacing the `measured` placeholders
- `analyze()` runs end to end on a real recorded WAV

Phase 2 (FastAPI service, React frontend with the two-question onboarding, teacher view, public deployment) gets its own plan once these numbers exist.
