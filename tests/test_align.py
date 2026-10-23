import wave

import pytest

from chorus.align import WordTiming, align_words


def test_word_timing_fields():
    t = WordTiming(word="cat", start=0.0, end=0.5, score=0.9)
    assert t.end > t.start


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        align_words(tmp_path / "nope.wav", "the cat sat on the mat")


def test_directory_path_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        align_words(tmp_path, "the cat")


def test_empty_text_returns_empty(silence_wav):
    assert align_words(silence_wav, "") == []


def test_digit_token_raises_value_error(silence_wav):
    with pytest.raises(ValueError, match="3"):
        align_words(silence_wav, "the 3 cats")


def test_all_offending_tokens_are_named(silence_wav):
    with pytest.raises(ValueError) as exc:
        align_words(silence_wav, "the 3 cat-sat")
    assert "'3'" in str(exc.value) and "'cat-sat'" in str(exc.value)


def test_hyphen_token_raises_value_error(silence_wav):
    with pytest.raises(ValueError, match="cat-sat"):
        align_words(silence_wav, "the cat-sat")


def test_non_ascii_token_raises_value_error(silence_wav):
    with pytest.raises(ValueError, match="caf"):
        align_words(silence_wav, "the caf\u00e9")


def test_validation_runs_after_missing_file_check(tmp_path):
    with pytest.raises(FileNotFoundError):
        align_words(tmp_path / "nope.wav", "the 3 cats")


def test_empty_text_skips_validation(silence_wav):
    assert align_words(silence_wav, "   ") == []


def _duration(path):
    with wave.open(str(path), "rb") as f:
        return f.getnframes() / f.getframerate()


TEXT = "the cat sat on the mat"


@pytest.mark.slow
def test_alignment_returns_one_timing_per_word(cat_wav):
    out = align_words(cat_wav, TEXT)
    assert [t.word for t in out] == TEXT.split()


@pytest.mark.slow
def test_timings_are_ordered_and_inside_audio(cat_wav):
    out = align_words(cat_wav, TEXT)
    dur = _duration(cat_wav)
    for prev, nxt in zip(out, out[1:]):
        assert prev.start < nxt.start
        assert prev.end <= nxt.start + 1e-6
    for t in out:
        assert 0 <= t.start < t.end <= dur + 0.02
    assert out[-1].end < dur - 0.3


@pytest.mark.slow
def test_scores_reflect_a_good_match(cat_wav):
    out = align_words(cat_wav, TEXT)
    assert sum(t.score for t in out) / len(out) > 0.5
    assert all(0.3 < t.score <= 1.0 for t in out)


@pytest.mark.slow
def test_scrambled_transcript_scores_lower(cat_wav):
    def mean(text):
        out = align_words(cat_wav, text)
        return sum(t.score for t in out) / len(out)

    assert mean(TEXT) - mean("mat the on sat cat the") >= 0.2


@pytest.mark.slow
def test_apostrophe_word_aligns(cat_wav):
    out = align_words(cat_wav, "the cat's")
    assert [t.word for t in out] == ["the", "cat's"]


@pytest.mark.slow
def test_model_bundle_is_cached_across_calls(cat_wav):
    """The ~2s rebuild cost (bundle.get_model()) must be paid once per
    process, not once per align_words call."""
    from chorus.align import _get_model_bundle

    _get_model_bundle.cache_clear()
    first = _get_model_bundle()
    align_words(cat_wav, TEXT)
    second = _get_model_bundle()
    assert first is second
    assert _get_model_bundle.cache_info().hits >= 1


def test_align_device_env_and_zerogpu(monkeypatch):
    """CHORUS_ALIGN_DEVICE wins; 'auto' never picks cuda on a ZeroGPU Space."""
    from chorus import align

    for env, zerogpu, expected in [("cpu", None, "cpu"), ("cuda", None, "cuda"), ("auto", "true", "cpu")]:
        monkeypatch.setenv("CHORUS_ALIGN_DEVICE", env)
        if zerogpu:
            monkeypatch.setenv("SPACES_ZERO_GPU", zerogpu)
        else:
            monkeypatch.delenv("SPACES_ZERO_GPU", raising=False)
        align._get_device.cache_clear()
        assert align._get_device() == expected
    monkeypatch.setenv("CHORUS_ALIGN_DEVICE", "gpu")
    align._get_device.cache_clear()
    with pytest.raises(ValueError):
        align._get_device()
    align._get_device.cache_clear()
