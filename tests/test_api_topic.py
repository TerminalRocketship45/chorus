"""Typed topics for POST /api/passages/generate (mocked model, no network)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from chorus_api import db, generate
from chorus_api.app import app
from tests.test_api_generate import GOOD_EL, FakeClient, reply


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHORUS_DB", str(tmp_path / "chorus.db"))
    monkeypatch.setenv("HF_TOKEN", "test-token")
    with TestClient(app) as c:
        yield c


def use(monkeypatch, replies):
    fake = FakeClient(replies)
    monkeypatch.setattr(generate, "_make_client", lambda token, model: fake)
    return fake


def gen(client, **body):
    r = client.post("/api/passages/generate", json={"band": "elementary", **body})
    assert r.status_code == 201, r.text
    return r.json()


def test_clean_topic():
    assert generate.clean_topic("  machine\x00 learning\n ") == "machine learning"
    assert len(generate.clean_topic("x" * 200)) == 80
    assert generate.clean_topic("   \x01 ") is None
    assert generate.clean_topic(5) is None
    assert '"' not in generate.clean_topic('say "hi" {now}')


def test_accepted_topic_is_used_and_stored(client, monkeypatch):
    fake = use(monkeypatch, [reply()])
    p = gen(client, topic="machine learning")
    assert p["source"] == "ai" and p["topic"] == "machine learning"
    assert p["requested_topic"] == "machine learning" and p["topic_accepted"] is True
    prompt = fake.kwargs[0]["messages"][1]["content"]
    assert "machine learning" in prompt and "declined" in prompt and "grades 2 to 5" in prompt
    assert db.get_generated_passage(p["id"])["topic"] == "machine learning"


def test_no_topic_keeps_old_behaviour(client, monkeypatch):
    use(monkeypatch, [reply()])
    p = gen(client, interests=["space"])
    assert p["topic"] == "space" and p["requested_topic"] is None and p["topic_accepted"] is True


@pytest.mark.parametrize("topic", ["guns", "Nazi history", "online casino"])
def test_blocklisted_topic_gives_library_passage(client, monkeypatch, topic):
    fake = use(monkeypatch, [reply()])
    p = gen(client, topic=topic)
    assert p["source"] == "library" and p["topic_accepted"] is False
    assert p["requested_topic"] == topic
    assert fake.calls == 0


def test_model_decline_gives_library_passage(client, monkeypatch):
    fake = use(monkeypatch, [json.dumps({"declined": True})])
    p = gen(client, topic="something odd")
    assert p["source"] == "library" and p["topic_accepted"] is False
    assert p["requested_topic"] == "something odd"
    assert fake.calls == 1


def test_model_failure_gives_library_passage(client, monkeypatch):
    use(monkeypatch, [RuntimeError("down")])
    p = gen(client, topic="volcanoes")
    assert p["source"] == "library" and p["topic_accepted"] is False


def test_no_token_with_topic(client, monkeypatch):
    monkeypatch.delenv("HF_TOKEN")
    p = gen(client, topic="volcanoes")
    assert p["source"] == "library" and p["topic_accepted"] is False


def test_non_text_topic_is_400(client):
    r = client.post("/api/passages/generate", json={"band": "elementary", "topic": 5})
    assert r.status_code == 400
