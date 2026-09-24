import json
from pathlib import Path

import pytest

from chorus.types import WordStatus
from eval.evaluate_l1_filter import (
    FilterMetrics,
    WordRecord,
    bootstrap_ci,
    build_records,
    evaluate,
    read_test_ids,
    sample_ids,
)
import eval.evaluate_l1_filter as E
from eval.fetch_speechocean import Utterance



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


# ---- additions (rulings R17-R20) ----

def _rec(expected, heard, acc, status=None, uttid=""):
    return WordRecord(expected, heard, acc, status, uttid)


def test_status_aware_flagging():
    # derived CORRECT
    m = evaluate([_rec("cat", "cat", 9.0)], "mandarin")
    assert (m.fp_before, m.tp_before) == (0, 0)
    # REPETITION with heard == expected: not flagged
    m = evaluate([_rec("cat", "cat", 9.0, WordStatus.REPETITION)], "mandarin")
    assert (m.fp_before, m.tp_before) == (0, 0)
    # SELF_CORRECTION: not flagged
    m = evaluate([_rec("cat", "cat", 9.0, WordStatus.SELF_CORRECTION)], "mandarin")
    assert (m.fp_before, m.tp_before) == (0, 0)
    # INSERTION: flagged, and never excused
    m = evaluate([_rec("cat", "cat", 9.0, WordStatus.INSERTION)], "mandarin")
    assert (m.fp_before, m.fp_after) == (1, 1)
    m = evaluate([_rec("cat", "cat", 1.0, WordStatus.INSERTION)], "mandarin")
    assert (m.tp_before, m.tp_after) == (1, 1)


def test_evaluate_consults_real_apply_l1_filter(monkeypatch):
    import chorus.pipeline as pipeline
    from dataclasses import replace

    calls = []

    def always_excuse(words, language):
        calls.append(language)
        return [replace(w, accent_excused=True) for w in words]

    monkeypatch.setattr(pipeline, "apply_l1_filter", always_excuse)
    m = evaluate(
        [_rec("cat", "dog", 9.0), _rec("cat", "dog", 1.0)],
        "mandarin",
    )
    assert calls
    assert (m.fp_before, m.fp_after) == (1, 0)
    assert (m.tp_before, m.tp_after) == (1, 0)


def _two_utterance_records():
    recs = []
    for i in range(20):
        recs.append(_rec("think", "sink", 9.0, uttid=f"a{i % 2}"))
        recs.append(_rec("cat", "dog", 9.0, uttid=f"a{i % 2}"))
        recs.append(_rec("cat", "dog", 2.0, uttid=f"b{i % 2}"))
        recs.append(_rec("think", "sink", 2.0, uttid=f"b{i % 2}"))
    return recs


def test_bootstrap_ci_deterministic_and_brackets_point():
    recs = _two_utterance_records()
    a = bootstrap_ci(recs, "mandarin", n=200, seed=3)
    b = bootstrap_ci(recs, "mandarin", n=200, seed=3)
    assert a == b
    m = evaluate(recs, "mandarin")
    for key, point in (("fp_reduction", m.fp_reduction), ("retention", m.retention)):
        lo, hi = a[key]
        assert lo <= point <= hi


def test_bootstrap_ci_degenerate_inputs():
    single = [_rec("think", "sink", 9.0, uttid="u")]
    out = bootstrap_ci(single, "mandarin", n=50, seed=0)
    assert out["fp_reduction"] == (1.0, 1.0)
    no_fp = [_rec("cat", "dog", 2.0, uttid="u"), _rec("cat", "dog", 2.0, uttid="v")]
    out = bootstrap_ci(no_fp, "mandarin", n=50, seed=0)
    assert out["retention"] == (1.0, 1.0)
    assert bootstrap_ci([], "mandarin", n=10, seed=0)["retention"] == (None, None)


def _utt(uttid, text, accs):
    words = [{"text": t.upper(), "accuracy": a} for t, a in zip(text.split(), accs)]
    return Utterance(uttid, text.upper(), 0, 0, 0, 0, words)


def _stub_transcribe(monkeypatch, mapping, counter):
    import chorus.asr as asr

    def fake(path, model_size="base.en"):
        counter.append(path)
        return asr.Transcript(text=mapping[Path(path).stem], duration_s=1.0)

    monkeypatch.setattr(asr, "transcribe", fake)


def test_build_records_pairing_safety_and_statuses(monkeypatch, tmp_path):
    utts = [
        _utt("U1", "think cat", [9.0, 3.0]),
        _utt("U2", "don't go", [9.0, 9.0]),
    ]
    # corpus word list disagrees with normalisation for U3 (hyphen splits)
    bad = Utterance("U3", "WELL-KNOWN DOG", 0, 0, 0, 0,
                    [{"text": "WELL-KNOWN", "accuracy": 9.0}, {"text": "DOG", "accuracy": 9.0}])
    utts.append(bad)
    index = {"u1": tmp_path / "u1.wav", "u2": tmp_path / "u2.wav", "u3": tmp_path / "u3.wav"}
    calls = []
    _stub_transcribe(monkeypatch, {"u1": "sink cat", "u2": "don't go", "u3": "well known dog"}, calls)
    recs, info = build_records(utts, index, cache_path=tmp_path / "c.json", model_size="base.en", return_info=True)
    assert info["skipped"] == 1 and info["skip_reasons"]
    assert [r.uttid for r in recs] == ["U1", "U1", "U2", "U2"]
    assert recs[0].status is WordStatus.SUBSTITUTION and recs[0].heard == "sink"
    assert recs[1].status is WordStatus.CORRECT
    assert recs[0].expected == "think"


def test_build_records_token_count_mismatch_is_skipped(monkeypatch, tmp_path):
    u = _utt("U1", "one two", [9.0])  # 2 tokens in text, 1 corpus word
    _stub_transcribe(monkeypatch, {"u1": "one two"}, [])
    recs, info = build_records([u], {"u1": tmp_path / "u1.wav"}, cache_path=tmp_path / "c.json", return_info=True)
    assert recs == [] and info["skipped"] == 1


def test_sample_test_ids_deterministic_and_from_test_only():
    test_ids = [f"{i:09d}" for i in range(1000)]
    a = sample_ids(test_ids, 50, 0)
    b = sample_ids(list(reversed(test_ids)), 50, 0)
    assert a == b and len(set(a)) == 50 and set(a) <= set(test_ids)
    assert sample_ids(test_ids, 50, 1) != a
    assert len(sample_ids(test_ids[:10], 50, 0)) == 10


def test_read_test_ids_parses_kaldi_text(tmp_path):
    (tmp_path / "text").write_text("000030012\tMARK IS\n000030024\tKATE\n", encoding="utf-8")
    assert read_test_ids(tmp_path) == ["000030012", "000030024"]


def test_transcript_cache_reused_and_written_incrementally(monkeypatch, tmp_path):
    utts = [_utt(f"U{i}", "cat", [9.0]) for i in range(3)]
    index = {f"u{i}": tmp_path / f"u{i}.wav" for i in range(3)}
    calls = []
    _stub_transcribe(monkeypatch, {f"u{i}": "cat" for i in range(3)}, calls)
    cache = tmp_path / "t.json"
    build_records(utts, index, cache_path=cache, save_every=1)
    assert len(calls) == 3
    assert set(json.loads(cache.read_text())) == {"u0", "u1", "u2"}
    calls.clear()
    recs = build_records(utts, index, cache_path=cache, save_every=1)
    assert calls == [] and len(recs) == 3


def test_cache_saved_before_failure(monkeypatch, tmp_path):
    import chorus.asr as asr

    utts = [_utt(f"U{i}", "cat", [9.0]) for i in range(3)]
    index = {f"u{i}": tmp_path / f"u{i}.wav" for i in range(3)}

    def flaky(path, model_size="base.en"):
        if Path(path).stem == "u2":
            raise RuntimeError("boom")
        return asr.Transcript(text="cat", duration_s=1.0)

    monkeypatch.setattr(asr, "transcribe", flaky)
    cache = tmp_path / "t.json"
    with pytest.raises(RuntimeError):
        build_records(utts, index, cache_path=cache, save_every=100)
    assert set(json.loads(cache.read_text())) == {"u0", "u1"}


# ---- fix round 1 (R21) ----

def _utt_recs(uttid, n_fp_excused=0, n_fp_kept=0):
    """Expert-correct false positives: think->sink is excused, cat->dog is kept."""
    return (
        [WordRecord("think", "sink", 9.0, uttid=uttid) for _ in range(n_fp_excused)]
        + [WordRecord("cat", "dog", 9.0, uttid=uttid) for _ in range(n_fp_kept)]
    )


def _word_level_ci(records, n, seed):
    import random

    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        m = evaluate([rng.choice(records) for _ in records], "mandarin")
        if m.fp_before:
            vals.append(m.fp_reduction)
    vals.sort()
    return E._percentile(vals, 0.025), E._percentile(vals, 0.975)


def test_bootstrap_uses_pooled_ratio_not_mean_of_utterance_ratios():
    # One big utterance (40 kept flags, ratio 0) and nine tiny ones (1 excused
    # flag each, ratio 1). Pooled point = 9/49; the mean of per-utterance ratios
    # would be 0.9. The pooled estimator's interval reaches far down; a
    # mean-of-ratios bootstrap would have a lower bound near 0.6-0.7.
    recs = _utt_recs("big", n_fp_kept=40)
    for i in range(9):
        recs += _utt_recs(f"s{i}", n_fp_excused=1)
    m = evaluate(recs, "mandarin")
    assert m.fp_reduction == pytest.approx(9 / 49)
    lo, hi = bootstrap_ci(recs, "mandarin", n=1000, seed=0)["fp_reduction"]
    assert lo < 0.3
    assert lo < m.fp_reduction < hi
    assert hi - lo > 0.5


def test_bootstrap_heterogeneous_point_is_pooled_and_interval_has_width():
    recs = _utt_recs("a", n_fp_excused=1)
    recs += _utt_recs("b", n_fp_kept=9)
    recs += _utt_recs("c", n_fp_excused=2, n_fp_kept=2)
    m = evaluate(recs, "mandarin")
    assert m.fp_reduction == pytest.approx(3 / 14)  # pooled, not mean(1, 0, .5) = .5
    lo, hi = bootstrap_ci(recs, "mandarin", n=500, seed=1)["fp_reduction"]
    assert hi > lo


def test_bootstrap_resamples_utterances_not_words():
    # Six utterances of ten flags each, either all excused or none: flags are
    # perfectly clustered, so the honest utterance-level interval is far wider
    # than a word-level bootstrap over the same 60 words would suggest.
    recs = []
    for i in range(3):
        recs += _utt_recs(f"e{i}", n_fp_excused=10)
        recs += _utt_recs(f"k{i}", n_fp_kept=10)
    lo, hi = bootstrap_ci(recs, "mandarin", n=1000, seed=0)["fp_reduction"]
    wlo, whi = _word_level_ci(recs, 1000, 0)
    assert (hi - lo) > 2 * (whi - wlo)
    assert (hi - lo) > 0.5


# main() tests

def _install_main_stubs(monkeypatch, tmp_path, scores, test_ids, train_ids, transcripts):
    import chorus.asr as asr
    import eval.fetch_speechocean as fs

    requested, transcribed = [], []
    monkeypatch.setattr(fs, "load_scores", lambda *a, **k: scores)
    monkeypatch.setattr(
        fs, "build_audio_index",
        lambda *a, **k: {u.uttid.lower(): tmp_path / f"{u.uttid.lower()}.wav" for u in scores},
    )

    def fake_split(split):
        requested.append(split)
        return {"test": test_ids, "train": train_ids}[split]

    monkeypatch.setattr(E, "split_ids", fake_split)
    monkeypatch.setattr(E, "CACHE_DIR", tmp_path / "cache")

    def fake_transcribe(path, model_size="base.en"):
        transcribed.append(Path(path).stem)
        return asr.Transcript(text=transcripts[Path(path).stem], duration_s=1.0)

    monkeypatch.setattr(asr, "transcribe", fake_transcribe)
    return requested, transcribed


def test_main_raises_on_zero_records(monkeypatch, tmp_path):
    bad = Utterance("T1", "WELL-KNOWN DOG", 0, 0, 0, 0,
                    [{"text": "WELL-KNOWN", "accuracy": 9.0}, {"text": "DOG", "accuracy": 9.0}])
    _install_main_stubs(monkeypatch, tmp_path, [bad], ["T1"], [], {"t1": "well known dog"})
    with pytest.raises(RuntimeError, match="No records"):
        E.main(["--limit", "5", "--results", str(tmp_path / "r.json")])
    assert not (tmp_path / "r.json").exists()


def test_main_empty_sample_raises(monkeypatch, tmp_path):
    _install_main_stubs(monkeypatch, tmp_path, [], [], [], {})
    with pytest.raises(RuntimeError, match="No records"):
        E.main(["--results", str(tmp_path / "r.json")])


def test_main_prints_na_for_undefined_ratios(monkeypatch, tmp_path, capsys):
    # Every word read and heard correctly: no false positives, no genuine errors.
    u = _utt("T1", "cat dog", [9.0, 9.0])
    _install_main_stubs(monkeypatch, tmp_path, [u], ["T1"], [], {"t1": "cat dog"})
    E.main(["--results", str(tmp_path / "r.json")])
    out = capsys.readouterr().out
    assert out.count("n/a (0 of 0)") == 2
    assert "UNDEFINED" in out
    fp_line = [l for l in out.splitlines() if l.startswith("false-positive reduction:")][0]
    ret_line = [l for l in out.splitlines() if l.startswith("genuine-error retention")][0]
    assert "0.0%" not in fp_line and "0.0%" not in ret_line
    res = json.loads((tmp_path / "r.json").read_text())
    assert res["fp_reduction"] is None and res["retention"] is None


def test_main_uses_test_split_and_records_settings(monkeypatch, tmp_path):
    scores = [
        _utt("T1", "think cat", [9.0, 2.0]),
        _utt("T2", "think cat", [9.0, 2.0]),
        _utt("R1", "think cat", [9.0, 2.0]),
        _utt("R2", "think cat", [9.0, 2.0]),
    ]
    transcripts = {u: "sink dog" for u in ("t1", "t2", "r1", "r2")}
    requested, transcribed = _install_main_stubs(
        monkeypatch, tmp_path, scores, ["T1", "T2"], ["R1", "R2"], transcripts
    )
    E.main(["--model", "tiny.en", "--limit", "10", "--seed", "7",
            "--language", "mandarin", "--results", str(tmp_path / "r.json")])
    assert requested == ["test"]
    assert sorted(transcribed) == ["t1", "t2"]
    res = json.loads((tmp_path / "r.json").read_text())
    assert (res["split"], res["seed"], res["model"], res["language"], res["limit"]) == (
        "test", 7, "tiny.en", "mandarin", 10)
    assert res["fp_before"] == 2 and res["fp_after"] == 0
    assert res["tp_before"] == 2 and res["tp_after"] == 2
    assert "tiny.en" in res["limitations"]
    assert res["baseline_false_flag_rate_on_expert_correct"] == {
        "rate": 1.0, "fp": 2, "expert_correct": 2}
    assert (tmp_path / "r.json").read_text().endswith("\n")


def test_summarise_limitations_and_digit_counts():
    recs = [
        WordRecord("four", "4", 10.0, uttid="a"),      # digit rendering false flag
        WordRecord("cat", "c4t", 10.0, uttid="a"),     # digit inside, not a number word
        WordRecord("opened", "open", 5.0, uttid="a"),  # genuine error wrongly excused
        WordRecord("think", "sink", 9.0, uttid="a"),   # excused false positive
    ]
    s = E.summarise(recs, "mandarin", 0, n_boot=20, model="base.en")
    assert s["digit_rendering_false_flags"] == 1
    assert s["false_flags_with_any_digit_in_heard"] == 2
    assert s["genuine_errors_excused"] == 1
    assert "1 of 1 genuine errors" in s["limitations"]
    assert "Mandarin-L1 only" in s["limitations"] and "base.en" in s["limitations"]


def test_missing_cmudict_fails_before_transcription(monkeypatch, tmp_path):
    def missing():
        raise RuntimeError("python -m nltk.downloader cmudict")

    calls = []
    _install_main_stubs(monkeypatch, tmp_path, [_utt("T1", "cat", [9.0])], ["T1"], [], {"t1": "cat"})
    import chorus.asr as asr
    monkeypatch.setattr(asr, "transcribe", lambda *a, **k: calls.append(1))
    monkeypatch.setattr(E, "_cmu_words", missing)
    with pytest.raises(RuntimeError, match="nltk.downloader cmudict"):
        E.main(["--results", str(tmp_path / "r.json")])
    assert calls == []


def test_cmu_words_error_is_actionable(monkeypatch):
    import nltk.corpus

    class Broken:
        def dict(self):
            raise LookupError("resource cmudict not found")

    monkeypatch.setattr(nltk.corpus, "cmudict", Broken())
    with pytest.raises(RuntimeError, match="nltk.downloader cmudict"):
        E._cmu_words()


def test_evaluate_unknown_language_raises():
    with pytest.raises(KeyError):
        evaluate([], "klingon")
