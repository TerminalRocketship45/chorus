"""The real-pipeline check (no mocking): posts tests/fixtures/the_cat_sat.wav,
and the same audio re-encoded to webm/opus via PyAV, through POST
/api/analyze, and checks every word comes back correct.

None of the 12 bundled passages' text is "The cat sat on the mat." (the
fixture's spoken text), so this monkeypatches chorus_api.passages.get_passage
for one test-only passage id rather than adding a throwaway entry to the real
passage set that the frontend would otherwise list.
"""
import av
import pytest
from fastapi.testclient import TestClient

from chorus_api import passages as passages_mod
from chorus_api.app import app
from chorus_api.passages import Passage

CAT_WAV = "tests/fixtures/the_cat_sat.wav"
CAT_TEXT = "The cat sat on the mat."
TEST_PASSAGE_ID = "test-cat-sat"


def _wav_to_webm_opus(src_path, dst_path) -> None:
    in_c = av.open(str(src_path))
    try:
        astream = next(s for s in in_c.streams if s.type == "audio")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)
        out_c = av.open(str(dst_path), mode="w", format="webm")
        out_stream = out_c.add_stream("libopus", rate=48000)
        try:
            for frame in in_c.decode(astream):
                for rframe in resampler.resample(frame):
                    for packet in out_stream.encode(rframe):
                        out_c.mux(packet)
            for rframe in resampler.resample(None):
                for packet in out_stream.encode(rframe):
                    out_c.mux(packet)
            for packet in out_stream.encode(None):
                out_c.mux(packet)
        finally:
            out_c.close()
    finally:
        in_c.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHORUS_DB", str(tmp_path / "chorus.db"))
    fake = Passage(
        id=TEST_PASSAGE_ID,
        title="test fixture (not a real passage)",
        band="elementary",
        level=1,
        topic="test",
        text=CAT_TEXT,
        word_count=6,
    )
    real_get_passage = passages_mod.get_passage

    def fake_get_passage(passage_id):
        return fake if passage_id == TEST_PASSAGE_ID else real_get_passage(passage_id)

    monkeypatch.setattr(passages_mod, "get_passage", fake_get_passage)
    with TestClient(app) as c:
        yield c


@pytest.mark.slow
def test_wav_through_real_pipeline_every_word_correct(client):
    with open(CAT_WAV, "rb") as f:
        resp = client.post(
            "/api/analyze",
            files={"audio": ("cat.wav", f, "audio/wav")},
            data={"passage_id": TEST_PASSAGE_ID},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [w["status"] for w in body["words"]] == ["correct"] * 6
    assert [w["display"] for w in body["words"]] == ["correct"] * 6
    assert body["score"]["accuracy"] == 1.0
    assert all(w["start"] is not None and w["end"] is not None for w in body["words"])


@pytest.mark.slow
def test_webm_opus_through_real_pipeline_every_word_correct(client, tmp_path):
    webm_path = tmp_path / "cat.webm"
    _wav_to_webm_opus(CAT_WAV, webm_path)

    with open(webm_path, "rb") as f:
        resp = client.post(
            "/api/analyze",
            files={"audio": ("cat.webm", f, "audio/webm")},
            data={"passage_id": TEST_PASSAGE_ID},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [w["status"] for w in body["words"]] == ["correct"] * 6
    assert body["score"]["accuracy"] == 1.0
