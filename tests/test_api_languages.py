import pytest
from fastapi.testclient import TestClient

from chorus_api import languages
from chorus_api.app import app

EXPECTED = [
    {"code": "somali", "label": "Somali", "support": "rules"},
    {"code": "spanish", "label": "Spanish", "support": "rules"},
    {"code": "mandarin", "label": "Mandarin Chinese", "support": "measured"},
    {"code": "hmong", "label": "Hmong", "support": "not_yet"},
    {"code": "karen", "label": "Karen", "support": "not_yet"},
    {"code": "english", "label": "English only", "support": "not_needed"},
    {"code": "other", "label": "Another language", "support": "not_yet"},
]


def test_route_matches_docs_exactly():
    with TestClient(app) as client:
        r = client.get("/api/languages")
    assert r.status_code == 200
    assert r.json() == EXPECTED


def test_list_languages_matches_docs():
    assert languages.list_languages() == EXPECTED


def test_known_codes():
    assert languages.known_codes() == {e["code"] for e in EXPECTED}


@pytest.mark.parametrize("code", ["somali", "spanish", "mandarin"])
def test_engine_language_passes_through_measured_and_rules(code):
    assert languages.engine_language(code) == code


@pytest.mark.parametrize("code", ["hmong", "karen", "english", "other"])
def test_engine_language_is_none_for_not_yet_and_not_needed(code):
    assert languages.engine_language(code) is None


def test_engine_language_none_in_none_out():
    assert languages.engine_language(None) is None


def test_engine_language_unknown_code_raises_key_error():
    with pytest.raises(KeyError):
        languages.engine_language("klingon")
