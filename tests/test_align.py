import wave

import pytest

from chorus.align import WordTiming, align_words


def test_word_timing_fields():
    t = WordTiming(word="cat", start=0.0, end=0.5, score=0.9)
    assert t.end > t.start


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        align_words(tmp_path / "nope.wav", "the cat sat on the mat")


def test_empty_text_returns_empty(silence_wav):
    assert align_words(silence_wav, "") == []


@pytest.mark.slow
def test_alignment_returns_one_timing_per_word(cat_wav):
    out = align_words(cat_wav, "the cat sat on the mat")
    assert len(out) == 6
    assert [t.word for t in out] == ["the", "cat", "sat", "on", "the", "mat"]


@pytest.mark.slow
def test_timings_are_monotonic(cat_wav):
    out = align_words(cat_wav, "the cat sat on the mat")
    for prev, nxt in zip(out, out[1:]):
        assert prev.start <= nxt.start


@pytest.mark.slow
def test_timings_lie_within_audio(cat_wav):
    with wave.open(str(cat_wav), "rb") as f:
        duration = f.getnframes() / f.getframerate()
    for t in align_words(cat_wav, "the cat sat on the mat"):
        assert 0 <= t.start < t.end <= duration + 0.05


@pytest.mark.slow
def test_scores_are_probabilities(cat_wav):
    for t in align_words(cat_wav, "the cat sat on the mat"):
        assert 0.0 <= t.score <= 1.0
