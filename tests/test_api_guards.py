"""Hallucination, loudness and debug-capture guards on the analyze path. No model needed."""
from __future__ import annotations

import json
import wave
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from chorus import asr, pipeline
from chorus.types import Analysis, ReadingScore, WordResult, WordStatus
from chorus_api import audio
from chorus_api import app as app_mod
from chorus_api.app import _heard_fraction, app

CAT_WAV = "tests/fixtures/the_cat_sat.wav"


def write_wav(path, x, rate=16000):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate)
        f.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


# ------------------------------------------------------------------ ASR segment filter


class FakeModel:
    def __init__(self, segs):
        self.segs, self.kwargs = segs, {}

    def transcribe(self, path, **kw):
        self.kwargs = kw
        return iter(self.segs), SimpleNamespace(duration=8.0)


def seg(text, nsp, lp, start=0.0, end=1.0):
    return SimpleNamespace(text=f" {text} ", no_speech_prob=nsp, avg_logprob=lp, start=start, end=end)


@pytest.fixture
def fake_model(monkeypatch, tmp_path):
    holder = {}
    monkeypatch.setattr(asr, "_get_model", lambda size: holder["m"])
    p = tmp_path / "a.wav"
    write_wav(p, np.zeros(1600))
    return holder, p


def test_hallucinated_segments_are_dropped_when_asked(fake_model):
    holder, p = fake_model
    holder["m"] = FakeModel([seg("the cat sat", 0.05, -0.3), seg("subs www zeoranger co uk", 0.9, -1.6)])
    t = asr.transcribe(p, drop_hallucinations=True)
    assert t.text == "the cat sat" and t.dropped_segments == 1 and len(t.segments) == 2
    t = asr.transcribe(p)  # default unchanged
    assert t.text == "the cat sat subs www zeoranger co uk" and t.dropped_segments == 0


def test_only_both_signals_together_drop_a_segment(fake_model):
    holder, p = fake_model
    holder["m"] = FakeModel([seg("a", 0.8, -0.2), seg("b", 0.1, -1.9), seg("c", 0.61, -1.01)])
    assert asr.transcribe(p, drop_hallucinations=True).text == "a b"


def test_a_confident_lone_you_on_silence_is_dropped(fake_model):
    holder, p = fake_model
    holder["m"] = FakeModel([seg("You", 0.92, -0.59)])
    assert asr.transcribe(p, drop_hallucinations=True).text == ""


def test_vad_filter_is_passed_through_and_off_by_default(fake_model):
    holder, p = fake_model
    holder["m"] = FakeModel([])
    asr.transcribe(p)
    assert holder["m"].kwargs["vad_filter"] is False
    asr.transcribe(p, vad_filter=True)
    assert holder["m"].kwargs["vad_filter"] is True


def test_pipeline_forwards_new_options(monkeypatch):
    seen = {}

    def fake(path, model_size="base.en", **kw):
        seen.update(kw)
        return asr.Transcript(text="the cat sat", duration_s=2.0, dropped_segments=2)

    monkeypatch.setattr(pipeline, "transcribe", fake)
    monkeypatch.setattr(pipeline, "align_words", lambda p, t: [])
    monkeypatch.setattr(pipeline, "_is_alignable", lambda t: False)
    a = pipeline.analyze(CAT_WAV, "the cat sat", vad_filter=True, drop_hallucinations=True)
    assert seen == {"vad_filter": True, "drop_hallucinations": True}
    assert a.transcript == "the cat sat" and a.dropped_segments == 2


# ------------------------------------------------------------------ loudness


def test_levels_and_normalise(tmp_path):
    p = tmp_path / "q.wav"
    t = np.arange(16000) / 16000
    write_wav(p, 0.01 * np.sin(2 * np.pi * 220 * t))  # peak -40 dBFS
    assert audio.wav_levels(p)["peak_dbfs"] == pytest.approx(-40.0, abs=0.2)
    gain = audio.normalize_wav_peak(p)
    assert gain == pytest.approx(37.0, abs=0.3)
    assert audio.wav_levels(p)["peak_dbfs"] == pytest.approx(-3.0, abs=0.2)
    loud = tmp_path / "l.wav"
    write_wav(loud, 0.8 * np.sin(2 * np.pi * 220 * t))
    assert audio.normalize_wav_peak(loud) == 0.0


def test_digital_silence_levels(tmp_path):
    p = tmp_path / "s.wav"
    write_wav(p, np.zeros(16000))
    assert audio.wav_levels(p)["peak_dbfs"] == -120.0
    assert audio.normalize_wav_peak(p) == 0.0


# ------------------------------------------------------------------ analyze endpoint


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHORUS_DB", str(tmp_path / "chorus.db"))
    monkeypatch.delenv("CHORUS_DEBUG_AUDIO_DIR", raising=False)
    with TestClient(app) as c:
        yield c


def W(i, e, h, st):
    return WordResult(index=i, expected=e, heard=h, status=st)


def analysis(words, transcript="x"):
    n = len(words)
    sc = ReadingScore(accuracy=0.5, wcpm=40.0, total_words=n, correct_words=n // 2, duration_s=5.0, long_pauses=0)
    return Analysis(words=words, score=sc, accent_adjusted=None, transcript=transcript)


def post(client, monkeypatch, result, wav=CAT_WAV):
    seen = {}

    def fake(path, *a, **k):
        seen["level"] = audio.wav_levels(path)
        return result

    monkeypatch.setattr(pipeline, "analyze", fake)
    with open(wav, "rb") as f:
        r = client.post("/api/analyze", files={"audio": ("a.wav", f, "audio/wav")},
                        data={"passage_id": "el-01"})
    return r, seen


def test_heard_fraction_rule():
    ws = [W(0, "the", "the", WordStatus.CORRECT), W(1, "cat", "kat", WordStatus.SUBSTITUTION),
          W(2, "sat", "zebra", WordStatus.SUBSTITUTION), W(3, "on", None, WordStatus.OMISSION)]
    assert _heard_fraction(ws) == 0.5
    assert _heard_fraction([]) == 0.0


def test_invented_text_from_silence_is_rejected(client, monkeypatch):
    words = [W(i, w, h, WordStatus.SUBSTITUTION if h else WordStatus.OMISSION)
             for i, (w, h) in enumerate(zip(
                 "one two three four five six seven eight nine ten".split(),
                 ["subs", "www", None, None, None, None, None, None, None, None]))]
    r, _ = post(client, monkeypatch, analysis(words, "subs www"))
    assert r.status_code == 422
    assert "couldn't hear enough reading" in r.json()["detail"]


def test_reading_with_many_errors_is_still_scored(client, monkeypatch):
    # 3 of 20 heard (exactly the 15% floor, and the 3-word minimum): still scored
    words = [W(i, "word", "word", WordStatus.CORRECT) for i in range(3)] + [
        W(i, "word", None, WordStatus.OMISSION) for i in range(3, 20)]
    r, _ = post(client, monkeypatch, analysis(words, "the"))
    assert r.status_code == 200 and r.json()["transcript"] == "the"


def test_one_or_two_stray_words_are_rejected_even_when_most_were_reached(client, monkeypatch):
    # An early-stop with only 2 words heard: fraction of reached is 100% but 2 < 3 words.
    words = [W(i, "word", "word", WordStatus.CORRECT) for i in range(2)] + [
        W(i, "word", None, WordStatus.NOT_REACHED) for i in range(2, 60)]
    r, _ = post(client, monkeypatch, analysis(words, "word word"))
    assert r.status_code == 422


def test_near_silent_recording_is_rejected_before_analysis(client, monkeypatch, tmp_path):
    p = tmp_path / "quiet.wav"
    write_wav(p, 0.0005 * np.random.default_rng(0).standard_normal(32000))  # about -64 dBFS
    called = []
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: called.append(1))
    with open(p, "rb") as f:
        r = client.post("/api/analyze", files={"audio": ("a.wav", f, "audio/wav")},
                        data={"passage_id": "el-01"})
    assert r.status_code == 422 and "very quiet" in r.json()["detail"] and not called


def test_quiet_recording_is_normalised_before_transcription(client, monkeypatch, tmp_path):
    p = tmp_path / "quiet.wav"
    x, = [np.sin(2 * np.pi * 200 * np.arange(32000) / 16000) * 0.02]  # -34 dBFS
    write_wav(p, x)
    words = [W(i, "the", "the", WordStatus.CORRECT) for i in range(3)]
    r, seen = post(client, monkeypatch, analysis(words), wav=str(p))
    assert r.status_code == 200
    assert seen["level"]["peak_dbfs"] == pytest.approx(-3.0, abs=0.3)


def test_debug_capture_off_by_default(client, monkeypatch, tmp_path):
    words = [W(i, "the", "the", WordStatus.CORRECT) for i in range(3)]
    r, _ = post(client, monkeypatch, analysis(words))
    assert r.status_code == 200
    assert not list(tmp_path.glob("**/*.upload"))


def test_debug_capture_saves_upload_wav_and_json(client, monkeypatch, tmp_path):
    d = tmp_path / "dbg"
    monkeypatch.setenv("CHORUS_DEBUG_AUDIO_DIR", str(d))
    words = [W(i, "the", "the", WordStatus.CORRECT) for i in range(3)]
    r, _ = post(client, monkeypatch, analysis(words, "the"))
    assert r.status_code == 200
    files = sorted(p.suffix for p in d.iterdir())
    assert files == [".json", ".upload", ".wav"]
    meta = json.loads(next(d.glob("*.json")).read_text())
    assert meta["passage_id"] == "el-01" and meta["transcript"] == "the"
    assert meta["options"]["beam_size"] == 5 and meta["words"][0]["expected"] == "the"
    assert "peak_dbfs" in meta["levels"] and "normalize_gain_db" in meta


def test_debug_capture_also_saves_rejections(client, monkeypatch, tmp_path):
    d = tmp_path / "dbg"
    monkeypatch.setenv("CHORUS_DEBUG_AUDIO_DIR", str(d))
    words = [W(0, "the", None, WordStatus.OMISSION)]
    r, _ = post(client, monkeypatch, analysis(words, ""))
    assert r.status_code == 422
    assert json.loads(next(d.glob("*.json")).read_text())["rejected"]


def test_default_model_is_small_en(monkeypatch):
    monkeypatch.delenv("CHORUS_ASR_MODEL", raising=False)
    assert app_mod._model_size() == "small.en"


def test_heard_fraction_ignores_not_reached_words():
    ws = [W(i, "word", "word", WordStatus.CORRECT) for i in range(3)] + [
        W(i, "word", None, WordStatus.NOT_REACHED) for i in range(3, 40)]
    assert _heard_fraction(ws) == 1.0


def test_short_honest_reading_of_a_long_passage_is_scored(client, monkeypatch):
    words = [W(i, "word", "word", WordStatus.CORRECT) for i in range(5)] + [
        W(i, "word", None, WordStatus.NOT_REACHED) for i in range(5, 60)]
    r, _ = post(client, monkeypatch, analysis(words, "word word word word word"))
    assert r.status_code == 200
    body = r.json()
    assert body["words"][10]["display"] == "not_reached"
    assert body["practice_words"] == []


def test_silence_is_still_rejected_with_unreached_support(client, monkeypatch):
    words = [W(i, "word", None, WordStatus.OMISSION) for i in range(60)]
    r, _ = post(client, monkeypatch, analysis(words, ""))
    assert r.status_code == 422
