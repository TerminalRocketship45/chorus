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
    assert bootstrap_ci([], "mandarin", n=10, seed=0)["retention"] == (0.0, 0.0)


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
