import re

import pytest
from fastapi.testclient import TestClient

from chorus.miscue import normalize
from chorus_api import passages
from chorus_api.app import app

# Mirrors chorus.pipeline._is_alignable / chorus.align._ALIGNABLE: the aligner
# only times [a-z'] tokens with at least one letter.
_ALIGNABLE = re.compile(r"[a-z']*[a-z][a-z']*")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_passage_counts_per_band():
    assert len([p for p in passages.load_passages() if p.band == "elementary"]) == 11
    assert len([p for p in passages.load_passages() if p.band == "secondary"]) == 12


def test_ids_follow_band_prefix():
    for p in passages.load_passages():
        prefix = "el-" if p.band == "elementary" else "se-"
        assert p.id.startswith(prefix), p.id


def test_elementary_word_counts_in_range():
    for p in passages.list_passages("elementary"):
        assert 40 <= p.word_count <= 80, (p.id, p.word_count)


def test_secondary_word_counts_in_range():
    for p in passages.list_passages("secondary"):
        assert 80 <= p.word_count <= 130, (p.id, p.word_count)


def test_levels_are_one_to_three():
    for p in passages.load_passages():
        assert p.level in (1, 2, 3)


def test_word_count_matches_normalize_length():
    for p in passages.load_passages():
        assert p.word_count == len(normalize(p.text))


def test_every_passage_normalizes_to_only_alignable_tokens():
    """Engine constraint: numbers as words, no hyphens, no non-ASCII — every
    token the aligner will see must match [a-z']+ with at least one letter."""
    for p in passages.load_passages():
        tokens = normalize(p.text)
        bad = [t for t in tokens if not _ALIGNABLE.fullmatch(t)]
        assert bad == [], f"{p.id} has unalignable tokens: {bad}"


def test_text_has_no_digits_hyphens_or_non_ascii():
    for p in passages.load_passages():
        assert not any(ch.isdigit() for ch in p.text), p.id
        assert "-" not in p.text, p.id
        assert all(ord(ch) < 128 for ch in p.text), p.id


def test_get_passage_unknown_id_returns_none():
    assert passages.get_passage("nope-99") is None


def test_list_passages_bad_band_raises_value_error():
    with pytest.raises(ValueError):
        passages.list_passages("bogus")


def test_route_returns_both_bands_by_default(client):
    r = client.get("/api/passages")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 23
    assert {p["id"] for p in body if p["band"] == "elementary"} == {
        f"el-{i:02d}" for i in range(1, 12)
    }


def test_route_filters_by_band(client):
    r = client.get("/api/passages?band=secondary")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 12
    assert all(p["band"] == "secondary" for p in body)


def test_route_includes_word_count_and_text(client):
    r = client.get("/api/passages?band=elementary")
    body = r.json()
    el01 = next(p for p in body if p["id"] == "el-01")
    assert el01["word_count"] == len(normalize(el01["text"]))
    assert el01["title"]
    assert el01["topic"]


def test_route_unknown_band_is_400(client):
    r = client.get("/api/passages?band=bogus")
    assert r.status_code == 400
    assert "detail" in r.json()


def test_route_get_one_passage_by_id(client):
    r = client.get("/api/passages/el-01")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "el-01"
    assert body["band"] == "elementary"
    assert body["word_count"] == len(normalize(body["text"]))


def test_route_get_one_passage_matches_list_item(client):
    list_body = client.get("/api/passages?band=secondary").json()
    se01_from_list = next(p for p in list_body if p["id"] == "se-01")
    r = client.get("/api/passages/se-01")
    assert r.json() == se01_from_list


def test_route_get_unknown_passage_is_404(client):
    r = client.get("/api/passages/nope-99")
    assert r.status_code == 404
    assert "detail" in r.json()
