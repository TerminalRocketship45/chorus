"""fallback_reason, server log lines, draft repairs, reply parsing, model list, library
featured passages. Mocked model, no network."""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from chorus_api import generate, passages
from chorus_api.app import app
from tests.test_api_generate import GOOD_EL, GOOD_SE, FakeClient, reply

SECRET = "hf_SECRETSECRETSECRET1234"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHORUS_DB", str(tmp_path / "chorus.db"))
    monkeypatch.setenv("HF_TOKEN", SECRET)
    monkeypatch.delenv("CHORUS_PASSAGE_MODEL", raising=False)
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


def warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


# ------------------------------------------------------------ fallback_reason


def test_ai_passage_has_null_reason(client, monkeypatch):
    use(monkeypatch, [reply()])
    assert gen(client, interests=["space"])["fallback_reason"] is None


def test_reason_no_token(client, monkeypatch, caplog):
    monkeypatch.delenv("HF_TOKEN")
    with caplog.at_level(logging.WARNING, logger="chorus_api.generate"):
        p = gen(client, interests=["space"])
    assert p["source"] == "library" and p["fallback_reason"] == "no_token"
    assert any("no_token" in m and "HF_TOKEN" in m for m in warnings(caplog))


def test_reason_topic_rejected(client, monkeypatch, caplog):
    use(monkeypatch, [reply()])
    with caplog.at_level(logging.WARNING, logger="chorus_api.generate"):
        p = gen(client, topic="guns")
    assert p["fallback_reason"] == "topic_rejected"
    assert any("topic_rejected" in m for m in warnings(caplog))


def test_reason_model_declined(client, monkeypatch, caplog):
    use(monkeypatch, [json.dumps({"declined": True})])
    with caplog.at_level(logging.WARNING, logger="chorus_api.generate"):
        p = gen(client, topic="odd thing")
    assert p["fallback_reason"] == "model_declined"
    assert any("model_declined" in m for m in warnings(caplog))


def test_reason_model_unavailable_logs_error_without_token(client, monkeypatch, caplog):
    exc = RuntimeError(f"402 Payment Required for token {SECRET}")
    exc.response = SimpleNamespace(status_code=402)
    fake = use(monkeypatch, [exc])
    with caplog.at_level(logging.INFO, logger="chorus_api.generate"):
        p = gen(client, interests=["space"])
    assert p["source"] == "library" and p["fallback_reason"] == "model_unavailable"
    assert fake.calls == 1
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "model_unavailable" in text and "RuntimeError" in text and "HTTP 402" in text
    assert SECRET not in text


def test_reason_model_unavailable_tries_next_model(client, monkeypatch):
    seen = []

    def make(token, model):
        seen.append(model)
        return FakeClient([RuntimeError("model not supported")]) if len(seen) == 1 else FakeClient([reply()])

    monkeypatch.setattr(generate, "_make_client", make)
    p = gen(client, interests=["space"])
    assert p["source"] == "ai" and p["fallback_reason"] is None
    assert seen == list(generate.DEFAULT_MODELS[:2])


def test_reason_client_cannot_be_made(client, monkeypatch):
    def boom(token, model):
        raise ImportError("no huggingface_hub")

    monkeypatch.setattr(generate, "_make_client", boom)
    assert gen(client)["fallback_reason"] == "model_unavailable"


def test_reason_invalid_output_logs_problems(client, monkeypatch, caplog):
    use(monkeypatch, [reply(text="Too short.")])
    with caplog.at_level(logging.WARNING, logger="chorus_api.generate"):
        p = gen(client, interests=["music"])
    assert p["source"] == "library" and p["fallback_reason"] == "invalid_output"
    assert any("invalid_output" in m and "words, need" in m for m in warnings(caplog))


def test_unparseable_reply_is_invalid_output(client, monkeypatch):
    use(monkeypatch, ["I cannot help."])
    assert gen(client)["fallback_reason"] == "invalid_output"


def test_scrub_removes_tokens():
    assert SECRET not in generate.scrub(f"bad {SECRET} and hf_abcdefghij", SECRET)
    assert len(generate.scrub("x" * 1000)) < 400


# ------------------------------------------------------------ repairs


def repaired(text, band="elementary", title="Night Sky"):
    d = generate.make_draft(json.dumps({"title": title, "text": text}), band, "space")
    return d


def test_repair_curly_quotes_and_dashes():
    d = repaired(GOOD_EL.replace("Every evening", "Every evening—always—").replace("She counted", "“She’s counted"))
    assert d.problems == [], d.problems
    assert "—" not in d.text and "“" not in d.text and "She's counted" in d.text.replace('"', "")


def test_repair_hyphens():
    d = repaired(GOOD_EL.replace("small gray", "small, well-known gray") )
    assert d.problems == [] and "well known" in d.text and "-" not in d.text
    assert "hyphens replaced" in d.repairs


def test_repair_digits_to_words():
    d = repaired(GOOD_EL + " She was 9 and he was 12 and they saw 100 stars, 50% bright.")
    assert d.problems == [], d.problems
    assert "nine" in d.text and "twelve" in d.text and "one hundred" in d.text and "fifty percent" in d.text


@pytest.mark.parametrize("bad", ["in 2024.", "1,000 stars.", "3.5 miles.", "the 5th star."])
def test_unfixable_digits_still_rejected(bad):
    d = repaired(GOOD_EL + " It was " + bad)
    assert any("digits" in p for p in d.problems), (bad, d.text)


def test_repair_markdown_and_surrounding_quotes():
    d = repaired('"**' + GOOD_EL.replace("A small", "# A small", 1) + '**"')
    assert d.problems == [], d.problems
    assert "*" not in d.text and "#" not in d.text and not d.text.startswith('"')
    assert "markdown removed" in d.repairs


def test_repair_bullets():
    d = repaired("- " + GOOD_EL)
    assert d.problems == [] and d.text == GOOD_EL


def test_repair_accents_folded_but_other_scripts_rejected():
    d = repaired(GOOD_EL.replace("school", "café"))
    assert d.problems == [] and "cafe" in d.text and "accents folded to ASCII" in d.repairs
    d = repaired(GOOD_EL + " 你好 is hello.")
    assert any("non-ASCII" in p for p in d.problems)


def test_repair_whitespace():
    d = repaired("  " + GOOD_EL.replace(". ", ".\n\n   "))
    assert d.problems == [] and "\n" not in d.text and "  " not in d.text


def test_trim_long_draft_at_sentence_end():
    sentence = "The little rocket flew over the quiet town tonight."  # 9 words
    text = " ".join([sentence] * 14)  # 126 words > 100
    d = repaired(text)
    assert d.problems == [] and "trimmed to a sentence end" in d.repairs
    assert len(generate.normalize(d.text)) <= 100 and d.text.endswith(".")
    assert len(generate.normalize(d.text)) == 99


def test_trim_drops_unfinished_last_sentence():
    d = repaired(GOOD_EL + " And then the moon began to")
    assert d.problems == [] and d.text == GOOD_EL


def test_too_long_with_no_sentence_ends_is_rejected():
    d = repaired(" ".join(["word"] * 130))
    assert any("words, need" in p for p in d.problems)


def test_blocklist_stays_strict_after_repair():
    d = repaired(GOOD_EL + " The soldier will kill it.")
    assert any("unsafe" in p for p in d.problems)


def test_title_repaired_and_defaulted():
    d = generate.make_draft(json.dumps({"title": "**“Night-Sky 2”**", "text": GOOD_EL}), "elementary", "space")
    assert d.title == "Night Sky two" and d.problems == []
    d = generate.make_draft(json.dumps({"title": "", "text": GOOD_EL}), "elementary", "machine learning")
    assert d.title == "Machine Learning" and d.problems == []


# ------------------------------------------------------------ parsing


def test_parse_json_in_prose_and_fence():
    raw = 'Sure, here you go!\n```json\n{"title": "Night Sky", "text": "' + GOOD_EL + '"}\n```\nEnjoy.'
    assert generate.parse_response(raw) == ("Night Sky", GOOD_EL)


def test_parse_single_quotes_and_trailing_comma():
    raw = "{'title': 'Night Sky', 'text': '" + GOOD_EL.replace("'", "") + "',}"
    assert generate.parse_response(raw) == ("Night Sky", GOOD_EL.replace("'", ""))
    raw = '{"title": "Night Sky", "text": "' + GOOD_EL + '",}'
    assert generate.parse_response(raw) == ("Night Sky", GOOD_EL)


def test_parse_literal_newlines_inside_json_string():
    raw = '{"title": "T", "text": "' + GOOD_EL.replace(". ", ".\n") + '"}'
    assert generate.parse_response(raw) == ("T", GOOD_EL)


def test_parse_title_line_plus_paragraph():
    assert generate.parse_response("Night Sky\n\n" + GOOD_EL) == ("Night Sky", GOOD_EL)
    assert generate.parse_response("**Title: Night Sky**\n" + GOOD_EL) == ("Night Sky", GOOD_EL)
    assert generate.parse_response("# Night Sky\n" + GOOD_EL) == ("Night Sky", GOOD_EL)


def test_parse_paragraph_only_has_no_title_and_long_first_line_is_text():
    assert generate.parse_response(GOOD_EL) == ("", GOOD_EL)
    t, x = generate.parse_response("Here is a title that is far too long for a title\n" + GOOD_EL)
    assert t == "" and x.startswith("Here is")


def test_parse_failures():
    for raw in ("", "not json at all", None, '{"title": "x"}'):
        with pytest.raises(ValueError):
            generate.parse_response(raw)


def test_is_declined_variants():
    assert generate.is_declined('Sorry. {"declined": true}')
    assert generate.is_declined("{'declined': True,}")
    assert not generate.is_declined(reply())


def test_plain_reply_generates_end_to_end(client, monkeypatch):
    use(monkeypatch, ["Night Sky\n\n" + GOOD_EL])
    p = gen(client, interests=["space"])
    assert p["source"] == "ai" and p["title"] == "Night Sky"


# ------------------------------------------------------------ models and client


def test_models_env_list(monkeypatch):
    monkeypatch.setenv("CHORUS_PASSAGE_MODEL", " a/b , c/d,")
    assert generate.models() == ["a/b", "c/d"]
    monkeypatch.delenv("CHORUS_PASSAGE_MODEL")
    assert generate.models() == list(generate.DEFAULT_MODELS)
    assert "mistralai/Mistral-7B-Instruct-v0.3" not in generate.DEFAULT_MODELS


def test_make_client_arguments(monkeypatch):
    import huggingface_hub

    seen = {}

    class Fake:
        def __init__(self, **kw):
            seen.update(kw)

    monkeypatch.setattr(huggingface_hub, "InferenceClient", Fake)
    generate._make_client("tok", "m/x")
    assert seen == {"model": "m/x", "provider": "auto", "token": "tok", "timeout": 30.0}


def test_real_inference_client_accepts_our_arguments():
    from huggingface_hub import InferenceClient

    c = generate._make_client("hf_notreal", "meta-llama/Llama-3.1-8B-Instruct")
    assert isinstance(c, InferenceClient) and c.provider == "auto" and c.timeout == 30.0


def test_none_content_is_unusable_not_a_crash(client, monkeypatch):
    fake = FakeClient([None])
    fake.chat_completion = lambda **kw: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
    )
    monkeypatch.setattr(generate, "_make_client", lambda t, m: fake)
    assert gen(client)["fallback_reason"] == "model_unavailable"


# ------------------------------------------------------------ library


def test_cac_passages_listed_first(client):
    for band, pid in (("elementary", "cac-01"), ("secondary", "cac-02")):
        lst = client.get(f"/api/passages?band={band}").json()
        assert lst[0]["id"] == pid and lst[0]["title"] == "The Congressional App Challenge"
        assert client.get(f"/api/passages/{pid}").json()["band"] == band
    both = client.get("/api/passages").json()
    assert both[0]["id"] == "cac-01"
    el = passages.get_passage("cac-01")
    se = passages.get_passage("cac-02")
    assert 60 <= el.word_count <= 80 and 90 <= se.word_count <= 120
    for p in (el, se):
        assert generate.validate_passage(p.text, p.band, p.title) == []
        assert p.text.isascii() and "Fourth District" in p.text


def test_fallback_never_picks_featured_passage(monkeypatch):
    for _ in range(60):
        assert not generate.library_fallback("elementary", ["science"], [])["id"].startswith("cac-")
