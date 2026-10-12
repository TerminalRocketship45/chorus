"""POST /api/analyze, with chorus.pipeline.analyze mocked so these tests need
no model (ASR / aligner). The slow, real-pipeline test lives in
tests/test_api_analyze_slow.py.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from chorus import pipeline
from chorus.types import Analysis, ReadingScore, WordResult, WordStatus
from chorus_api import db
from chorus_api.app import app
from chorus_api.concurrency import AnalysisBusy

CAT_WAV = "tests/fixtures/the_cat_sat.wav"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHORUS_DB", str(tmp_path / "chorus.db"))
    with TestClient(app) as c:
        yield c


def _fake_analyze_factory(language_seen: list):
    def fake_analyze(audio_path, expected_text, language=None, model_size="base.en"):
        language_seen.append(language)
        words = [
            WordResult(index=0, expected="the", heard="the", status=WordStatus.CORRECT, start=0.0, end=0.1),
            WordResult(
                index=1,
                expected="cat",
                heard="kat",
                status=WordStatus.SUBSTITUTION,
                start=0.1,
                end=0.2,
                accent_excused=bool(language),
            ),
            WordResult(index=2, expected="sat", heard=None, status=WordStatus.OMISSION),
        ]
        score = ReadingScore(
            accuracy=2 / 3, wcpm=50.0, total_words=3, correct_words=2, duration_s=2.0, long_pauses=0
        )
        adjusted = None
        if language:
            adjusted = ReadingScore(
                accuracy=1.0, wcpm=90.0, total_words=3, correct_words=3, duration_s=2.0, long_pauses=0
            )
        return Analysis(words=words, score=score, accent_adjusted=adjusted)

    return fake_analyze


def _post_analyze(client, monkeypatch, **data):
    language_seen: list = []
    monkeypatch.setattr(pipeline, "analyze", _fake_analyze_factory(language_seen))
    with open(CAT_WAV, "rb") as f:
        resp = client.post(
            "/api/analyze",
            files={"audio": ("cat.wav", f, "audio/wav")},
            data=data,
        )
    return resp, language_seen


def test_analyze_without_student_or_language(client, monkeypatch):
    resp, seen = _post_analyze(client, monkeypatch, passage_id="el-01")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session_id"] is None
    assert body["home_language"] is None
    assert body["accent_filter_applied"] is False
    assert body["accent_adjusted"] is None
    assert seen == [None]
    assert body["practice_words"] == ["cat", "sat"]
    assert [w["display"] for w in body["words"]] == ["correct", "misread", "skipped"]


def test_analyze_with_measured_language_applies_accent_filter(client, monkeypatch):
    resp, seen = _post_analyze(client, monkeypatch, passage_id="el-01", home_language="mandarin")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert seen == ["mandarin"]
    assert body["home_language"] == "mandarin"
    assert body["accent_filter_applied"] is True
    assert body["accent_adjusted"] is not None
    assert body["words"][1]["display"] == "accent_ok"


def test_analyze_with_not_yet_language_does_not_reach_engine(client, monkeypatch):
    """hmong has no rule file; the code must never be forwarded as `language`."""
    resp, seen = _post_analyze(client, monkeypatch, passage_id="el-01", home_language="hmong")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert seen == [None]
    assert body["home_language"] == "hmong"
    assert body["accent_filter_applied"] is False
    assert body["accent_adjusted"] is None


def test_analyze_home_language_echoes_sent_code_regardless_of_support(client, monkeypatch):
    """docs/api.md: home_language echoes the code sent, whatever its support
    level (e.g. "english", not_needed), and is null only when none was given
    at all — never substituted or omitted just because the engine can't use it."""
    resp, seen = _post_analyze(client, monkeypatch, passage_id="el-01", home_language="english")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert seen == [None]
    assert body["home_language"] == "english"
    assert body["accent_filter_applied"] is False


def test_analyze_home_language_is_null_only_when_none_given_at_all(client, monkeypatch):
    resp, seen = _post_analyze(client, monkeypatch, passage_id="el-01")
    assert resp.status_code == 200, resp.text
    assert resp.json()["home_language"] is None
    assert seen == [None]


def test_analyze_session_id_is_null_when_no_student_id_given(client, monkeypatch):
    resp, _ = _post_analyze(client, monkeypatch, passage_id="el-01", home_language="mandarin")
    assert resp.status_code == 200, resp.text
    assert resp.json()["session_id"] is None


def test_analyze_unknown_passage_is_400(client, monkeypatch):
    resp, _ = _post_analyze(client, monkeypatch, passage_id="nope-99")
    assert resp.status_code == 400


def test_analyze_missing_passage_id_is_400(client, monkeypatch):
    resp, _ = _post_analyze(client, monkeypatch)
    assert resp.status_code == 400


def test_analyze_missing_audio_is_400(client, monkeypatch):
    language_seen: list = []
    monkeypatch.setattr(pipeline, "analyze", _fake_analyze_factory(language_seen))
    resp = client.post("/api/analyze", data={"passage_id": "el-01"})
    assert resp.status_code == 400


def test_analyze_unknown_home_language_is_400(client, monkeypatch):
    resp, _ = _post_analyze(client, monkeypatch, passage_id="el-01", home_language="klingon")
    assert resp.status_code == 400


def test_analyze_bad_student_id_is_400(client, monkeypatch):
    resp, _ = _post_analyze(client, monkeypatch, passage_id="el-01", student_id="not-a-number")
    assert resp.status_code == 400


def test_analyze_unknown_student_id_is_400(client, monkeypatch):
    resp, _ = _post_analyze(client, monkeypatch, passage_id="el-01", student_id="999")
    assert resp.status_code == 400


def test_analyze_defaults_home_language_from_student(client, monkeypatch):
    student = client.post(
        "/api/students",
        json={"name": "Amina", "grade_band": "elementary", "home_language": "mandarin"},
    ).json()
    resp, seen = _post_analyze(client, monkeypatch, passage_id="el-01", student_id=str(student["id"]))
    assert resp.status_code == 200, resp.text
    assert seen == ["mandarin"]
    assert resp.json()["home_language"] == "mandarin"


def test_analyze_explicit_home_language_overrides_student(client, monkeypatch):
    student = client.post(
        "/api/students",
        json={"name": "Amina", "grade_band": "elementary", "home_language": "mandarin"},
    ).json()
    resp, seen = _post_analyze(
        client, monkeypatch, passage_id="el-01", student_id=str(student["id"]), home_language="spanish"
    )
    assert resp.status_code == 200, resp.text
    assert seen == ["spanish"]
    assert resp.json()["home_language"] == "spanish"


def test_analyze_saves_session_when_student_id_given(client, monkeypatch):
    student = client.post(
        "/api/students", json={"name": "Amina", "grade_band": "elementary"}
    ).json()
    resp, _ = _post_analyze(client, monkeypatch, passage_id="el-01", student_id=str(student["id"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["session_id"], int)

    detail = client.get(f"/api/students/{student['id']}").json()
    assert len(detail["sessions"]) == 1
    session = detail["sessions"][0]
    assert session["id"] == body["session_id"]
    assert session["passage_id"] == "el-01"
    assert session["passage_title"]
    assert session["score"] == body["score"]
    assert session["practice_words"] == body["practice_words"]
    assert session["accent_ok_count"] == 0  # no home_language in this test -> no accent_ok words


def test_analyze_no_student_id_does_not_save_a_session(client, monkeypatch):
    resp, _ = _post_analyze(client, monkeypatch, passage_id="el-01")
    assert resp.status_code == 200, resp.text
    assert resp.json()["session_id"] is None
    assert db.list_students() == []


def test_analyze_no_speech_heard_is_422(client, monkeypatch):
    def all_omitted(audio_path, expected_text, language=None, model_size="base.en"):
        words = [
            WordResult(index=0, expected="the", heard=None, status=WordStatus.OMISSION),
            WordResult(index=1, expected="cat", heard=None, status=WordStatus.OMISSION),
        ]
        score = ReadingScore(
            accuracy=0.0, wcpm=0.0, total_words=2, correct_words=0, duration_s=2.0, long_pauses=0
        )
        return Analysis(words=words, score=score, accent_adjusted=None)

    monkeypatch.setattr(pipeline, "analyze", all_omitted)
    with open(CAT_WAV, "rb") as f:
        resp = client.post(
            "/api/analyze",
            files={"audio": ("cat.wav", f, "audio/wav")},
            data={"passage_id": "el-01"},
        )
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_analyze_file_too_large_is_413(client, monkeypatch):
    language_seen: list = []
    monkeypatch.setattr(pipeline, "analyze", _fake_analyze_factory(language_seen))
    big = io.BytesIO(b"\x00" * (10 * 1024 * 1024 + 1))
    resp = client.post(
        "/api/analyze",
        files={"audio": ("big.wav", big, "audio/wav")},
        data={"passage_id": "el-01"},
    )
    assert resp.status_code == 413
    assert language_seen == []  # never reached the analyzer


def test_analyze_undecodable_audio_is_422(client, monkeypatch):
    language_seen: list = []
    monkeypatch.setattr(pipeline, "analyze", _fake_analyze_factory(language_seen))
    garbage = io.BytesIO(b"this is not an audio container, just text" * 10)
    resp = client.post(
        "/api/analyze",
        files={"audio": ("not_audio.bin", garbage, "application/octet-stream")},
        data={"passage_id": "el-01"},
    )
    assert resp.status_code == 422
    assert language_seen == []


def test_analyze_audio_too_long_is_413(client, monkeypatch, tmp_path):
    import wave

    language_seen: list = []
    monkeypatch.setattr(pipeline, "analyze", _fake_analyze_factory(language_seen))

    long_wav = tmp_path / "long.wav"
    with wave.open(str(long_wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        # 121 s of silence > the 120 s cap.
        f.writeframes(b"\x00\x00" * 16000 * 121)

    with open(long_wav, "rb") as f:
        resp = client.post(
            "/api/analyze",
            files={"audio": ("long.wav", f, "audio/wav")},
            data={"passage_id": "el-01"},
        )
    assert resp.status_code == 413
    assert language_seen == []


def test_analyze_503_when_gate_is_busy(client, monkeypatch):
    language_seen: list = []
    monkeypatch.setattr(pipeline, "analyze", _fake_analyze_factory(language_seen))

    async def busy_run(func, *args, **kwargs):
        raise AnalysisBusy("busy")

    import chorus_api.app as app_mod

    monkeypatch.setattr(app_mod._gate, "run", busy_run)
    with open(CAT_WAV, "rb") as f:
        resp = client.post(
            "/api/analyze",
            files={"audio": ("cat.wav", f, "audio/wav")},
            data={"passage_id": "el-01"},
        )
    assert resp.status_code == 503
    assert "detail" in resp.json()
