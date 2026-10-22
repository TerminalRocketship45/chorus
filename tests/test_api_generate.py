"""Interests, AI-written passages and per-student passage lists. No network:
the Hugging Face InferenceClient is replaced by a fake."""
from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from chorus import pipeline
from chorus.types import Analysis, ReadingScore, WordResult, WordStatus
from chorus_api import db, generate, interests, passages
from chorus_api.app import app

CAT_WAV = "tests/fixtures/the_cat_sat.wav"

GOOD_EL = (
    "A small gray rocket sat on the hill behind the school. Every evening Priya climbed up "
    "to look at the sky. She counted the bright planets and the tiny stars one by one. "
    "Her little sister held the flashlight and wrote down every number in a notebook. "
    "When the moon came up, they both smiled and waved at it."
)
GOOD_SE = " ".join(
    ["The observatory on the edge of town opened its doors every Friday night for anyone curious enough to climb the stairs."] * 1
    + ["Students took turns at the telescope while a volunteer explained what they were seeing."]
    + ["Rahel noticed a faint smudge of light that turned out to be a distant galaxy, millions of years old."]
    + ["She realized that she was looking at the past, and that the light had traveled longer than any person had ever lived."]
    + ["Walking home, she looked up differently, as if the sky had become a place she might someday know well."]
)


EXTRA = ("requested_topic", "topic_accepted")


def reply(title="Night Sky", text=GOOD_EL, fenced=False):
    raw = json.dumps({"title": title, "text": text})
    return f"```json\n{raw}\n```" if fenced else raw


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.kwargs = []

    def chat_completion(self, **kw):
        self.kwargs.append(kw)
        r = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        if isinstance(r, Exception):
            raise r
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=r))])


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHORUS_DB", str(tmp_path / "chorus.db"))
    monkeypatch.setenv("HF_TOKEN", "test-token")
    with TestClient(app) as c:
        yield c


def use_fake(monkeypatch, replies):
    fake = FakeClient(replies)
    monkeypatch.setattr(generate, "_make_client", lambda token, model: fake)
    return fake


# ---------------------------------------------------------------- validation


def test_good_passages_validate():
    assert generate.validate_passage(GOOD_EL, "elementary", "Night Sky") == []
    assert generate.validate_passage(GOOD_SE, "secondary") == []


@pytest.mark.parametrize(
    "bad,needle",
    [
        (GOOD_EL + " It was 7 o clock.", "digits"),
        (GOOD_EL + " A well-known star.", "hyphen"),
        (GOOD_EL + " The café was open.", "non-ASCII"),
    ],
)
def test_rejects_digits_hyphens_non_ascii(bad, needle):
    problems = generate.validate_passage(bad, "elementary")
    assert any(needle in p for p in problems), problems


def test_length_bounds():
    assert generate.validate_passage("Too short.", "elementary")
    assert generate.validate_passage(GOOD_EL, "secondary")  # elementary text, secondary band
    assert generate.validate_passage(" ".join(["word"] * 81), "elementary")
    assert not generate.validate_passage(" ".join(["word"] * 80), "elementary")


def test_title_and_blocklist():
    assert generate.validate_passage(GOOD_EL, "elementary", "one two three four five six seven eight nine")
    assert generate.validate_passage(GOOD_EL + " The soldier will kill it.", "elementary")


def test_curly_quotes_and_dashes_normalised():
    title, text = generate.parse_response(
        json.dumps({"title": "Mia’s Day", "text": "It’s “fun”—really."})
    )
    assert title == "Mia's Day"
    assert text == "It's \"fun\", really."


def test_parse_code_fenced_and_chatter():
    assert generate.parse_response(reply(fenced=True)) == ("Night Sky", GOOD_EL)
    assert generate.parse_response("Sure! " + reply() + " Enjoy.")[0] == "Night Sky"
    with pytest.raises(ValueError):
        generate.parse_response("not json at all")


def test_every_library_passage_validates():
    for p in passages.load_passages():
        assert generate.validate_passage(p.text, p.band, p.title) == [], p.id


def test_library_covers_every_interest_in_both_bands():
    for band in ("elementary", "secondary"):
        topics = {p.topic for p in passages.list_passages(band)}
        missing = interests.known_codes() - topics
        assert not missing, (band, missing)


def test_library_ids_follow_prefix_and_are_unique():
    ids = [p.id for p in passages.load_passages()]
    assert len(ids) == len(set(ids))
    assert all(i.startswith(("el-", "se-")) for i in ids)


# ---------------------------------------------------------------- generation


def test_generate_valid_json(client, monkeypatch):
    fake = use_fake(monkeypatch, [reply()])
    r = client.post("/api/passages/generate", json={"band": "elementary", "interests": ["space"]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source"] == "ai" and body["id"].startswith("g-")
    assert body["topic"] == "space" and body["band"] == "elementary"
    assert body["text"] == GOOD_EL and fake.calls == 1
    got = client.get(f"/api/passages/{body['id']}").json()
    assert {k: v for k, v in body.items() if k not in EXTRA} == got
    assert body["requested_topic"] is None and body["topic_accepted"] is True


def test_generate_code_fenced(client, monkeypatch):
    use_fake(monkeypatch, [reply(fenced=True)])
    r = client.post("/api/passages/generate", json={"band": "elementary", "interests": ["space"]})
    assert r.json()["source"] == "ai"


def test_generate_retries_then_succeeds(client, monkeypatch):
    fake = use_fake(monkeypatch, [reply(text="Too short."), RuntimeError("boom"), reply()])
    r = client.post("/api/passages/generate", json={"band": "elementary", "interests": ["space"]})
    assert r.json()["source"] == "ai" and fake.calls == 3


def test_generate_three_failures_fall_back_to_library(client, monkeypatch):
    fake = use_fake(monkeypatch, [reply(text=GOOD_EL + " It was 7 o clock.")])
    r = client.post("/api/passages/generate", json={"band": "elementary", "interests": ["music"]})
    assert r.status_code == 201
    body = r.json()
    assert fake.calls == 3
    assert body["source"] == "library" and body["id"].startswith("el-")
    assert body["topic"] == "music"


def test_fallback_respects_exclude_ids(client, monkeypatch):
    use_fake(monkeypatch, [RuntimeError("down")])
    # music has exactly one elementary passage; excluding it falls back to another one
    first = passages.list_passages("elementary")
    music = [p.id for p in first if p.topic == "music"]
    for _ in range(10):
        body = client.post(
            "/api/passages/generate",
            json={"band": "elementary", "interests": ["music"], "exclude_ids": music},
        ).json()
        assert body["id"] not in music and body["band"] == "elementary"


def test_no_token_goes_straight_to_fallback(client, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)

    def boom(token, model):
        raise AssertionError("must not create a client without a token")

    monkeypatch.setattr(generate, "_make_client", boom)
    r = client.post("/api/passages/generate", json={"band": "secondary", "interests": ["art"]})
    assert r.status_code == 201
    assert r.json()["source"] == "library" and r.json()["topic"] == "art"


def test_auth_error_does_not_retry(client, monkeypatch):
    exc = RuntimeError("unauthorised")
    exc.response = SimpleNamespace(status_code=402)
    fake = use_fake(monkeypatch, [exc])
    r = client.post("/api/passages/generate", json={"band": "elementary", "interests": ["food"]})
    assert r.json()["source"] == "library" and fake.calls == 1


def test_generate_uses_model_env_and_prompt(client, monkeypatch):
    monkeypatch.setenv("CHORUS_PASSAGE_MODEL", "some/model")
    seen = {}

    def make(token, model):
        seen["model"] = model
        return FakeClient([reply()])

    monkeypatch.setattr(generate, "_make_client", make)
    client.post("/api/passages/generate", json={"band": "elementary", "interests": ["space"]})
    assert seen["model"] == "some/model"
    msgs = generate.build_prompt("secondary", "Space")
    text = " ".join(m["content"] for m in msgs)
    assert "grades 6 to 12" in text and "between 80 and 130 words" in text and "space" in text


def test_generate_validation_errors(client):
    assert client.post("/api/passages/generate", json={"band": "middle"}).status_code == 400
    assert client.post(
        "/api/passages/generate", json={"band": "elementary", "interests": ["klingon"]}
    ).status_code == 400
    assert client.post(
        "/api/passages/generate", json={"band": "elementary", "student_id": 99}
    ).status_code == 400


def test_generated_passage_stored_for_student(client, monkeypatch):
    use_fake(monkeypatch, [reply()])
    s = client.post("/api/students", json={"name": "A", "grade_band": "elementary"}).json()
    g = client.post(
        "/api/passages/generate",
        json={"band": "elementary", "interests": ["space"], "student_id": s["id"]},
    ).json()
    lst = client.get(f"/api/students/{s['id']}/passages").json()
    assert [e["passage"]["id"] for e in lst] == [g["id"]]
    assert lst[0] == {"passage": {k: v for k, v in g.items() if k not in EXTRA}, "read": False, "attempts": 0, "last_result": None}
    # AI passages are not in the library list
    assert all(p["source"] == "library" for p in client.get("/api/passages").json())


def test_unknown_g_id_is_404(client):
    assert client.get("/api/passages/g-999").status_code == 404
    assert client.get("/api/passages/g-abc").status_code == 404


# ---------------------------------------------------------------- analyze with g-ids


def _fake_analyze(audio_path, expected_text, language=None, model_size="base.en", **options):
    words = [
        WordResult(index=i, expected=w, heard=w, status=WordStatus.CORRECT, start=0.1 * i, end=0.1 * i + 0.1)
        for i, w in enumerate(["a", "b", "c"])
    ]
    score = ReadingScore(accuracy=0.9, wcpm=70.0, total_words=1, correct_words=1, duration_s=2.0, long_pauses=0)
    adj = ReadingScore(accuracy=0.95, wcpm=72.0, total_words=1, correct_words=1, duration_s=2.0, long_pauses=0)
    _fake_analyze.texts.append(expected_text)
    return Analysis(words=words, score=score, accent_adjusted=adj if language else None)


_fake_analyze.texts = []


def _read(client, monkeypatch, passage_id, student_id):
    monkeypatch.setattr(pipeline, "analyze", _fake_analyze)
    with open(CAT_WAV, "rb") as f:
        return client.post(
            "/api/analyze",
            files={"audio": ("cat.wav", f, "audio/wav")},
            data={"passage_id": passage_id, "student_id": str(student_id)},
        )


def test_analyze_resolves_g_ids_and_student_passages(client, monkeypatch):
    use_fake(monkeypatch, [reply()])
    s = client.post(
        "/api/students", json={"name": "A", "grade_band": "elementary", "home_language": "somali"}
    ).json()
    g = client.post(
        "/api/passages/generate",
        json={"band": "elementary", "interests": ["space"], "student_id": s["id"]},
    ).json()
    _fake_analyze.texts.clear()
    r = _read(client, monkeypatch, g["id"], s["id"])
    assert r.status_code == 200, r.text
    assert _fake_analyze.texts == [GOOD_EL]
    assert r.json()["passage_id"] == g["id"] and r.json()["session_id"]
    _read(client, monkeypatch, g["id"], s["id"])
    _read(client, monkeypatch, "el-01", s["id"])  # a library passage read, never generated
    lst = client.get(f"/api/students/{s['id']}/passages").json()
    by_id = {e["passage"]["id"]: e for e in lst}
    assert set(by_id) == {g["id"], "el-01"}
    assert by_id[g["id"]]["read"] is True and by_id[g["id"]]["attempts"] == 2
    lr = by_id[g["id"]]["last_result"]
    assert lr["accuracy"] == 0.9 and lr["accent_adjusted_accuracy"] == 0.95 and lr["wcpm"] == 70.0
    assert lr["at"].endswith("Z")
    assert by_id["el-01"]["attempts"] == 1 and by_id["el-01"]["passage"]["source"] == "library"


def test_analyze_unknown_g_id_is_400(client, monkeypatch):
    s = client.post("/api/students", json={"name": "A", "grade_band": "elementary"}).json()
    assert _read(client, monkeypatch, "g-404", s["id"]).status_code == 400


def test_student_passages_unknown_student(client):
    assert client.get("/api/students/99/passages").status_code == 400


# ---------------------------------------------------------------- interests & students


def test_interests_route(client):
    body = client.get("/api/interests").json()
    assert [i["code"] for i in body] == [
        "animals", "sports", "space", "nature", "food", "music", "art", "science", "history", "adventure",
    ]
    assert body[0] == {"code": "animals", "label": "Animals"}


def test_student_interests_create_and_validate(client):
    r = client.post(
        "/api/students",
        json={"name": "A", "grade_band": "elementary", "interests": ["space", "animals", "space"]},
    )
    assert r.status_code == 201 and r.json()["interests"] == ["space", "animals"]
    assert client.post("/api/students", json={"name": "B", "grade_band": "elementary"}).json()["interests"] == []
    for bad in (["nope"], "space", [3]):
        assert client.post(
            "/api/students", json={"name": "C", "grade_band": "elementary", "interests": bad}
        ).status_code == 400
    listed = client.get("/api/students").json()
    assert listed[0]["interests"] == ["space", "animals"]
    assert client.get(f"/api/students/{listed[0]['id']}").json()["student"]["interests"] == ["space", "animals"]


def test_patch_student(client):
    s = client.post("/api/students", json={"name": "A", "grade_band": "elementary"}).json()
    url = f"/api/students/{s['id']}"
    r = client.patch(url, json={"interests": ["music"], "grade_band": "secondary"})
    assert r.status_code == 200
    body = r.json()
    assert body["interests"] == ["music"] and body["grade_band"] == "secondary" and body["name"] == "A"
    assert client.patch(url, json={"name": "Amina", "home_language": "somali"}).json()["home_language"] == "somali"
    assert client.patch(url, json={"home_language": None}).json()["home_language"] is None
    assert client.patch(url, json={"interests": ["bad"]}).status_code == 400
    assert client.patch(url, json={"grade_band": "x"}).status_code == 400
    assert client.patch(url, json={"name": " "}).status_code == 400
    assert client.patch(url, json={"home_language": "klingon"}).status_code == 400
    assert client.patch("/api/students/999", json={"name": "Z"}).status_code == 400
    assert client.get(url).json()["student"]["interests"] == ["music"]


# ---------------------------------------------------------------- migration


def test_migration_of_old_schema_db(tmp_path):
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE students (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, grade_band TEXT NOT NULL,
            home_language TEXT, created_at TEXT NOT NULL);
        INSERT INTO students (name, grade_band, home_language, created_at)
            VALUES ('Old', 'elementary', 'somali', '2026-01-01T00:00:00Z');
        """
    )
    conn.commit()
    conn.close()
    db.init_db(path)
    db.init_db(path)  # idempotent
    old = db.get_student(1, path)
    assert old["name"] == "Old" and old["interests"] == []
    assert db.update_student(1, {"interests": ["art"]}, path)["interests"] == ["art"]
    g = db.create_generated_passage("T", "elementary", "art", "Some text here.", path=path)
    assert g["id"] == "g-1" and g["level"] == 2 and g["student_id"] is None
    assert db.get_generated_passage("g-1", path)["title"] == "T"
