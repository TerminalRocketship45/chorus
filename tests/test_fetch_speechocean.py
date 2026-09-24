import io
import json
import tarfile
from pathlib import Path

import pytest

from eval.fetch_speechocean import (
    DEFAULT_DEST,
    Utterance,
    EXTRACTED_MARKER,
    build_audio_index,
    download,
    find_scores_json,
    load_scores,
    parse_scores,
)

SAMPLE = {
    "000010011": {
        "text": "MARK IS GOING TO SCHOOL",
        "accuracy": 8.0,
        "fluency": 9.0,
        "prosodic": 9.0,
        "total": 8.0,
        "words": [
            {
                "text": "MARK",
                "accuracy": 9.0,
                "stress": 10.0,
                "total": 9.0,
                "phones": ["M", "AA0", "R", "K"],
                "phones-accuracy": [2.0, 2.0, 1.0, 2.0],
            },
            {
                "text": "IS",
                "accuracy": 7.0,
                "stress": 10.0,
                "total": 7.0,
                "phones": ["IH1", "Z"],
                "phones-accuracy": [1.0, 2.0],
            },
        ],
    }
}


def test_parse_returns_utterances():
    out = parse_scores(SAMPLE)
    assert len(out) == 1
    assert isinstance(out[0], Utterance)


def test_parse_reads_sentence_scores():
    u = parse_scores(SAMPLE)[0]
    assert u.uttid == "000010011"
    assert u.accuracy == 8.0
    assert u.prosody == 9.0


def test_parse_keeps_word_detail():
    u = parse_scores(SAMPLE)[0]
    assert u.words[0]["text"] == "MARK"
    assert u.words[0]["phones-accuracy"] == [2.0, 2.0, 1.0, 2.0]


def test_parse_handles_empty_input():
    assert parse_scores({}) == []


def test_parse_keeps_second_word():
    u = parse_scores(SAMPLE)[0]
    assert [w["text"] for w in u.words] == ["MARK", "IS"]
    assert u.words[1]["phones"] == ["IH1", "Z"]


def test_build_audio_index_maps_lowercased_stems(tmp_path):
    (tmp_path / "top" / "WAVE" / "SPEAKER0001").mkdir(parents=True)
    (tmp_path / "top" / "WAVE" / "SPEAKER0002").mkdir(parents=True)
    a = tmp_path / "top" / "WAVE" / "SPEAKER0001" / "000010011.WAV"
    b = tmp_path / "top" / "WAVE" / "SPEAKER0002" / "000020022.wav"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    (tmp_path / "top" / "WAVE" / "SPEAKER0001" / "notes.txt").write_text("n")
    (tmp_path / "top" / "scores.json").write_text("{}")
    index = build_audio_index(tmp_path)
    assert index == {"000010011": a, "000020022": b}


def test_build_audio_index_lowercases_uppercase_stem(tmp_path):
    (tmp_path / "d").mkdir()
    p = tmp_path / "d" / "ABC123.WAV"
    p.write_bytes(b"x")
    assert build_audio_index(tmp_path) == {"abc123": p}


def test_find_scores_json_nested(tmp_path):
    nested = tmp_path / "speechocean762" / "resource"
    nested.mkdir(parents=True)
    (nested / "scores.json").write_text("{}")
    assert find_scores_json(tmp_path) == nested / "scores.json"


def test_load_scores_nested(tmp_path):
    nested = tmp_path / "speechocean762" / "test" / "deep"
    nested.mkdir(parents=True)
    (nested / "scores.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    out = load_scores(tmp_path)
    assert [u.uttid for u in out] == ["000010011"]


def test_missing_scores_json_raises_with_run_command(tmp_path):
    with pytest.raises(FileNotFoundError, match="python -m eval.fetch_speechocean"):
        find_scores_json(tmp_path)
    with pytest.raises(FileNotFoundError, match="python -m eval.fetch_speechocean"):
        load_scores(tmp_path)


def _tiny_tarball() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in (
            ("speechocean762/resource/scores.json", json.dumps(SAMPLE).encode()),
            ("speechocean762/WAVE/SPEAKER0001/000000001.WAV", b"RIFF" * 5000),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _place(dest: Path, data: bytes) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "speechocean762.tar.gz"
    archive.write_bytes(data)
    return archive


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network fetch attempted")

    monkeypatch.setattr("eval.fetch_speechocean._fetch_archive", boom)


def test_download_extracts_writes_marker_and_is_idempotent(
    tmp_path, no_network, monkeypatch
):
    dest = tmp_path / "corpus"
    _place(dest, _tiny_tarball())
    assert download(dest) == dest
    assert (dest / EXTRACTED_MARKER).exists()
    assert find_scores_json(dest).name == "scores.json"
    wav = dest / "speechocean762" / "WAVE" / "SPEAKER0001" / "000000001.WAV"
    assert wav.exists()
    wav.unlink()

    def boom(*a, **k):
        raise AssertionError("re-extracted")

    monkeypatch.setattr("eval.fetch_speechocean.tarfile.open", boom)
    assert download(dest) == dest
    assert not wav.exists()


def test_download_reextracts_when_marker_missing(tmp_path, no_network):
    dest = tmp_path / "corpus"
    _place(dest, _tiny_tarball())
    download(dest)
    wav = dest / "speechocean762" / "WAVE" / "SPEAKER0001" / "000000001.WAV"
    wav.unlink()
    (dest / EXTRACTED_MARKER).unlink()
    download(dest)
    assert wav.exists()
    assert (dest / EXTRACTED_MARKER).exists()


def test_download_truncated_archive_deleted_and_raises(tmp_path, no_network):
    dest = tmp_path / "corpus"
    data = _tiny_tarball()
    archive = _place(dest, data[: len(data) // 2])
    with pytest.raises(RuntimeError, match="python -m eval.fetch_speechocean"):
        download(dest)
    assert not archive.exists()
    assert not (dest / EXTRACTED_MARKER).exists()


def test_download_not_a_tar_deleted_and_raises(tmp_path, no_network):
    dest = tmp_path / "corpus"
    archive = _place(dest, b"<html>not a tarball</html>")
    with pytest.raises(RuntimeError):
        download(dest)
    assert not archive.exists()
    assert not (dest / EXTRACTED_MARKER).exists()


def test_build_audio_index_duplicate_stems_raise(tmp_path):
    for spk in ("A", "B"):
        (tmp_path / spk).mkdir()
    (tmp_path / "A" / "000001.WAV").write_bytes(b"x")
    (tmp_path / "B" / "000001.wav").write_bytes(b"x")
    with pytest.raises(ValueError, match="000001"):
        build_audio_index(tmp_path)


@pytest.mark.slow
def test_real_corpus_parses_and_audio_covered():
    try:
        find_scores_json(DEFAULT_DEST)
    except FileNotFoundError:
        pytest.skip("speechocean762 not downloaded")
    utts = load_scores(DEFAULT_DEST)
    assert len(utts) > 4900
    for u in utts:
        assert u.text.strip()
        assert len(u.words) >= 1
    index = build_audio_index(DEFAULT_DEST)
    missing = [u.uttid for u in utts if u.uttid.lower() not in index]
    coverage = 1 - len(missing) / len(utts)
    print(f"audio coverage {coverage:.4%}, missing {missing[:20]}")
    assert coverage >= 0.99
