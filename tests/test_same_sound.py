"""Same-sound (homophone) rule and opt-in recogniser option plumbing."""
from pathlib import Path

import pytest

from chorus.miscue import detect_miscues
from chorus.phonemes import same_sound
from chorus.types import WordStatus

import eval.evaluate_l1_filter as E


@pytest.mark.parametrize("a,b", [("two", "too"), ("their", "there"), ("its", "it's"), ("to", "too")])
def test_same_sound_true(a, b):
    assert same_sound(a, b)


@pytest.mark.parametrize(
    "a,b", [("rock", "lock"), ("opened", "open"), ("looked", "look"), ("cat", "cat"), ("zzqx", "zzqy")]
)
def test_same_sound_false(a, b):
    assert not same_sound(a, b)


def test_homophone_substitution_correct_only_when_on():
    off = detect_miscues(["i", "have", "two"], ["i", "have", "too"])
    assert off[2].status is WordStatus.SUBSTITUTION
    on = detect_miscues(["i", "have", "two"], ["i", "have", "too"], same_sound=True)
    assert on[2].status is WordStatus.CORRECT
    assert on[2].heard == "too"


@pytest.mark.parametrize("exp,heard", [("rock", "lock"), ("opened", "open")])
def test_different_word_not_excused(exp, heard):
    r = detect_miscues(["the", exp], ["the", heard], same_sound=True)
    assert r[1].status is WordStatus.SUBSTITUTION


def test_omission_unaffected():
    r = detect_miscues(["a", "two"], ["a"], same_sound=True)
    assert r[1].status is WordStatus.OMISSION


def test_cache_path_names(tmp_path):
    d = tmp_path
    assert E.cache_path_for("small.en", cache_dir=d).name == "transcripts_small.en.json"
    names = {
        E.cache_path_for("small.en", 5, cache_dir=d).name,
        E.cache_path_for("small.en", 5, True, cache_dir=d).name,
        E.cache_path_for("small.en", 1, True, cache_dir=d).name,
        E.cache_path_for("small.en", cache_dir=d).name,
    }
    assert len(names) == 4


def test_transcribe_options_reach_model(monkeypatch, tmp_path):
    import chorus.asr as asr

    seen = {}

    class FakeModel:
        def transcribe(self, path, **kw):
            seen.update(kw)
            return [], type("I", (), {"duration": 1.0})()

    monkeypatch.setattr(asr, "_get_model", lambda m: FakeModel())
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    asr.transcribe(wav)
    assert seen["beam_size"] == 1 and seen["initial_prompt"] is None
    asr.transcribe(wav, beam_size=5, initial_prompt="hello there")
    assert seen["beam_size"] == 5 and seen["initial_prompt"] == "hello there"


def test_build_records_plumbs_options(monkeypatch, tmp_path):
    import chorus.asr as asr
    from eval.fetch_speechocean import Utterance

    calls = []

    def fake(path, model_size="base.en", beam_size=1, initial_prompt=None, hotwords=None):
        calls.append((beam_size, initial_prompt))
        return asr.Transcript(text="i have too", duration_s=1.0)

    monkeypatch.setattr(asr, "transcribe", fake)
    words = [{"text": t, "accuracy": 10.0} for t in ("I", "HAVE", "TWO")]
    u = Utterance("u1", "I HAVE TWO", 0, 0, 0, 0, words)
    idx = {"u1": tmp_path / "u1.wav"}
    recs = E.build_records([u], idx, beam_size=5, same_sound=True, prompt_passage=True)
    assert calls == [(5, "I HAVE TWO")]
    assert recs[2].status is WordStatus.CORRECT
    recs = E.build_records([u], idx)
    assert recs[2].status is WordStatus.SUBSTITUTION


def test_digit_context_digit_by_digit_only_when_passage_does():
    from chorus.miscue import normalize

    exp = ["four", "nine", "five"]
    assert normalize("495") == ["four", "hundred", "ninety", "five"]
    assert normalize("495", digit_context=exp) == exp
    assert normalize("2891", digit_context=["two", "eight", "nine", "one"]) == [
        "two", "eight", "nine", "one"
    ]
    # Passage has no such digit run: default behaviour is unchanged.
    assert normalize("496", digit_context=exp) == normalize("496")
    # A wrong digit stays wrong (not forced to match).
    assert normalize("496", digit_context=exp) != exp
    # Passage that really says the cardinal wins.
    card = ["four", "hundred", "ninety", "five"]
    assert normalize("495", digit_context=card) == card


def test_analyze_plumbs_options(monkeypatch, tmp_path):
    import chorus.pipeline as pl
    from chorus.asr import Transcript

    seen = []

    def fake(path, model_size="base.en", **kw):
        seen.append(kw)
        return Transcript(text="i have too", duration_s=1.0)

    monkeypatch.setattr(pl, "transcribe", fake)
    monkeypatch.setattr(pl, "align_words", lambda *a, **k: [])
    monkeypatch.setattr(pl, "_attach_timings", lambda w, t, i: w)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    base = pl.analyze(wav, "I have two")
    assert seen[-1] == {} and base.words[2].status is WordStatus.SUBSTITUTION
    opt = pl.analyze(wav, "I have two", beam_size=5, same_sound=True, prompt_passage=True)
    assert seen[-1] == {"beam_size": 5, "initial_prompt": "I have two"}
    assert opt.words[2].status is WordStatus.CORRECT
