"""POST /api/feedback with a mocked Hugging Face client (no network)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from chorus_api import feedback, generate
from chorus_api.app import app


def W(i, expected, heard, status, display="ok", excused=False):
    return {"index": i, "expected": expected, "heard": heard, "status": status,
            "accent_excused": excused, "display": display}


WORDS = [
    W(0, "she", "she", "correct"),
    W(1, "walked", "walk", "substitution", "misread"),
    W(2, "through", "though", "substitution", "misread"),
    W(3, "island", None, "omission", "skipped"),
    W(4, "think", "sink", "substitution", "accent_ok", excused=True),
    W(5, "quietly", "quietly", "insertion", "extra_nearby"),
    W(6, "again", "again", "repetition"),
    W(7, "home", "home", "self_correction"),
]
SCORE = {"accuracy": 0.6, "wcpm": 72.4}
ADJ = {"accuracy": 0.75, "wcpm": 80.0}
GOOD = "You read at about 72 words correct per minute, which is a good pace. Nice work on the whole passage! Try practicing: through, island."


class FakeClient:
    def __init__(self, replies):
        self.replies, self.calls, self.kwargs = list(replies), 0, []

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


def post(client):
    return client.post("/api/feedback", json={
        "passage_id": "el-01", "home_language": "somali", "words": WORDS,
        "score": SCORE, "accent_adjusted": ADJ})


def use(monkeypatch, replies):
    fake = FakeClient(replies)
    monkeypatch.setattr(generate, "_make_client", lambda token, model: fake)
    return fake


def test_summary_excludes_accent_and_extra_nearby():
    s = feedback.summarize(WORDS, SCORE, ADJ)
    assert [m["word"] for m in s["misread_words"]] == ["walked", "through"]
    assert s["misread_words"][0]["heard"] == "walk"
    assert s["skipped_words"] == ["island"]
    assert (s["repeated_count"], s["self_corrected_count"]) == (1, 1)
    assert s["words_correct_per_minute"] == 72 and s["accuracy_percent"] == 60
    assert s["accuracy_percent_accent_adjusted"] == 75
    flat = str(s)
    assert "think" not in flat and "quietly" not in flat


def test_valid_reply_is_returned_as_ai(client, monkeypatch):
    fake = use(monkeypatch, [GOOD])
    body = post(client).json()
    assert body == {"feedback": GOOD, "source": "ai"}
    prompt = fake.kwargs[0]["messages"][1]["content"]
    assert "walked -> walk" in prompt and "island" in prompt
    assert "think" not in prompt and "quietly" not in prompt


@pytest.mark.parametrize("bad", [
    "Your accent made some words tricky. Try practicing: through, island.",
    "You may have dyslexia. Try practicing: through.",
    "Good reading! Try practicing: through, island, banana.",
    "Good reading! " + "Lots of words here. " * 20,
    "One sentence only.",
    "Nice. Good. Great. Fine. Done.",
])
def test_rule_breaking_reply_falls_back_to_template(client, monkeypatch, bad):
    s = feedback.summarize(WORDS, SCORE, ADJ)
    vocab = {w["expected"] for w in WORDS} | {"banana"}
    assert feedback.validate_reply(bad, s, vocab) is None
    use(monkeypatch, [bad])
    body = post(client).json()
    assert body["source"] == "template"


def test_practice_word_not_in_misread_set_is_rejected():
    s = feedback.summarize(WORDS, SCORE, ADJ)
    vocab = {w["expected"] for w in WORDS}
    bad = "Great pace today. Try practicing: through, walked, home."
    assert feedback.validate_reply(bad, s, vocab) is None


def test_no_token_gives_template(client, monkeypatch):
    monkeypatch.delenv("HF_TOKEN")
    body = post(client).json()
    assert body["source"] == "template"
    assert "72 words correct per minute" in body["feedback"]
    assert "Try practicing: walked, through, island." in body["feedback"]
    assert "accent" not in body["feedback"].lower()


def test_provider_error_gives_template(client, monkeypatch):
    use(monkeypatch, [RuntimeError("boom")])
    assert post(client).json()["source"] == "template"


def test_template_without_errors():
    s = feedback.summarize([W(0, "a", "a", "correct")], {"accuracy": 1.0, "wcpm": 100}, None)
    t = feedback.template(s)
    assert "Try practicing" not in t and "100 words correct per minute" in t


def test_bad_body_is_400(client):
    assert client.post("/api/feedback", json={"words": 3}).status_code == 400
