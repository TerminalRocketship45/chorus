import pytest

import chorus.pipeline as pipeline
from chorus.align import WordTiming
from chorus.asr import Transcript
from chorus.pipeline import _attach_timings, _is_alignable, analyze, apply_l1_filter
from chorus.types import Analysis, WordResult, WordStatus


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


@pytest.mark.parametrize("token", ["cat", "don't", "it's"])
def test_is_alignable_accepts_letter_tokens(token):
    assert _is_alignable(token) is True


@pytest.mark.parametrize("token", ["3", "cat-sat", "café", "'", ""])
def test_is_alignable_rejects_other_tokens(token):
    assert _is_alignable(token) is False


def _correct(index, expected):
    return WordResult(
        index=index, expected=expected, heard=expected, status=WordStatus.CORRECT
    )


def test_attach_timings_skips_unaligned_words():
    words = [_correct(0, "cat"), _correct(1, "3"), _correct(2, "sat")]
    timings = [WordTiming("cat", 0.1, 0.4, 0.9), WordTiming("sat", 0.6, 0.9, 0.9)]
    out = _attach_timings(words, timings, [0, 2])
    assert (out[0].start, out[0].end) == (0.1, 0.4)
    assert out[1].start is None and out[1].end is None
    assert (out[2].start, out[2].end) == (0.6, 0.9)


def test_attach_timings_rejects_length_mismatch():
    words = [_correct(0, "cat"), _correct(1, "sat")]
    with pytest.raises(ValueError):
        _attach_timings(words, [WordTiming("cat", 0.1, 0.4, 0.9)], [0, 1])


def test_attach_timings_does_not_mutate_input():
    words = [_correct(0, "cat")]
    out = _attach_timings(words, [WordTiming("cat", 0.1, 0.4, 0.9)], [0])
    assert words[0].start is None and words[0].end is None
    assert out[0] is not words[0]


def test_analyze_skips_alignment_when_no_token_is_alignable(monkeypatch, tmp_path):
    """Digit-only passages must not reach the aligner (regression)."""

    def boom(*args, **kwargs):
        raise AssertionError("align_words must not be called")

    monkeypatch.setattr(pipeline, "align_words", boom)
    monkeypatch.setattr(
        pipeline, "transcribe",
        lambda path, model_size="base.en": Transcript(
            text="one two three", duration_s=3.0
        ),
    )
    result = analyze(tmp_path / "unused.wav", "1 2 3")
    assert isinstance(result, Analysis)
    assert len(result.words) == 3
    assert all(w.start is None and w.end is None for w in result.words)


# The slow tests below prove plumbing only. The fixture is a synthetic voice,
# not a child or an accented reader, so they say nothing about accuracy on
# real learners.
PASSAGE = "The cat sat on the mat."


@pytest.mark.slow
def test_analyze_end_to_end_matching_text(cat_wav):
    result = analyze(cat_wav, PASSAGE, language="somali")
    assert len(result.words) == 6
    assert all(w.status is WordStatus.CORRECT for w in result.words)
    assert result.score.accuracy == 1.0
    assert all(w.start is not None and w.end is not None for w in result.words)
    assert all(w.start < w.end for w in result.words)
    starts = [w.start for w in result.words]
    assert all(a < b for a, b in zip(starts, starts[1:]))
    assert result.accent_adjusted is not None
    assert result.accent_adjusted.accuracy == 1.0
    assert result.score.wcpm > 0


@pytest.mark.slow
def test_analyze_without_language_has_no_adjusted_score(cat_wav):
    assert analyze(cat_wav, PASSAGE).accent_adjusted is None


@pytest.mark.slow
def test_analyze_mismatch_is_not_excused_for_somali(cat_wav):
    result = analyze(cat_wav, "The dog sat on the mat.", language="somali")
    errors = [w for w in result.words if w.status is not WordStatus.CORRECT]
    assert len(errors) == 1
    dog = errors[0]
    assert dog.expected == "dog"
    assert dog.status is WordStatus.SUBSTITUTION
    assert dog.heard == "cat"
    assert dog.accent_excused is False
    assert result.score.accuracy == pytest.approx(5 / 6)
    assert result.accent_adjusted.accuracy == pytest.approx(5 / 6)
