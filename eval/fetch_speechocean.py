"""Fetch and parse speechocean762.

5000 English utterances from 250 non-native speakers (all Mandarin L1, half
of them children), labelled by five experts at sentence, word and phoneme
level. Free for commercial and non-commercial use. This is the only labelled
non-native corpus available to us, which is why Mandarin is the sole
'validated' language in the spec.
"""
from __future__ import annotations

import json
import os
import tarfile
import urllib.request
import zlib
from dataclasses import dataclass
from pathlib import Path

CORPUS_URL = "https://www.openslr.org/resources/101/speechocean762.tar.gz"
DEFAULT_DEST = Path(__file__).parent / "data" / "speechocean762"
RUN_COMMAND = "python -m eval.fetch_speechocean"
EXTRACTED_MARKER = ".extracted"
_PROGRESS_STEP = 50 * 1024 * 1024


@dataclass
class Utterance:
    uttid: str
    text: str
    accuracy: float
    fluency: float
    prosody: float
    total: float
    words: list[dict]


def parse_scores(scores_json: dict) -> list[Utterance]:
    """Convert the corpus scores.json structure into Utterance records."""
    return [
        Utterance(
            uttid=uttid,
            text=entry["text"],
            accuracy=float(entry["accuracy"]),
            fluency=float(entry["fluency"]),
            prosody=float(entry["prosodic"]),
            total=float(entry["total"]),
            words=entry.get("words", []),
        )
        for uttid, entry in scores_json.items()
    ]


def find_scores_json(dest: Path = DEFAULT_DEST) -> Path:
    """Locate scores.json anywhere under dest (the archive layout is nested)."""
    if dest.exists():
        for path in sorted(dest.rglob("scores.json")):
            return path
    raise FileNotFoundError(
        f"scores.json not found under {dest}. Run: {RUN_COMMAND}"
    )


def _fetch_archive(archive: Path) -> None:
    """Download to <archive>.part, then atomically move into place."""
    part = archive.with_name(archive.name + ".part")
    print(f"Downloading {CORPUS_URL} ...", flush=True)
    downloaded = 0
    next_report = _PROGRESS_STEP
    with urllib.request.urlopen(CORPUS_URL, timeout=60) as resp, open(part, "wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            downloaded += len(chunk)
            if downloaded >= next_report:
                print(f"  {downloaded // (1024 * 1024)} MB", flush=True)
                next_report += _PROGRESS_STEP
    os.replace(part, archive)


def download(dest: Path = DEFAULT_DEST) -> Path:
    """Download and extract the corpus. Idempotent.

    Extraction is complete only when the ``.extracted`` marker exists; the
    marker is written after ``extractall`` returns, so an interrupted
    extraction is redone from the archive on the next run.
    """
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "speechocean762.tar.gz"
    marker = dest / EXTRACTED_MARKER
    if marker.exists():
        try:
            find_scores_json(dest)
            return dest
        except FileNotFoundError:
            pass
    if not archive.exists():
        _fetch_archive(archive)
    if not tarfile.is_tarfile(archive):
        archive.unlink()
        raise RuntimeError(
            f"{archive} was not a valid tar archive and has been deleted. "
            f"Re-run: {RUN_COMMAND}"
        )
    marker.unlink(missing_ok=True)
    print("Extracting ...", flush=True)
    try:
        with tarfile.open(archive) as tf:
            tf.extractall(dest, filter="data")
    except (tarfile.TarError, EOFError, OSError, zlib.error) as exc:
        archive.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        raise RuntimeError(
            f"Extracting {archive} failed ({type(exc).__name__}: {exc}); the "
            f"archive was deleted. Re-running `{RUN_COMMAND}` will "
            f"re-download it."
        ) from exc
    marker.write_text("ok\n", encoding="utf-8")
    return dest


def load_scores(dest: Path = DEFAULT_DEST) -> list[Utterance]:
    """Load the parsed score records from an already-downloaded corpus."""
    path = find_scores_json(dest)
    return parse_scores(json.loads(path.read_text(encoding="utf-8")))


def build_audio_index(dest: Path = DEFAULT_DEST) -> dict[str, Path]:
    """Map lower-cased utterance id (file stem) to its .wav/.WAV path.

    Walks the tree once. The ids are the keys of scores.json; look them up
    with ``index[uttid.lower()]``.
    """
    index: dict[str, Path] = {}
    for root, _dirs, files in os.walk(dest):
        for name in files:
            stem, ext = os.path.splitext(name)
            if ext.lower() == ".wav":
                key, path = stem.lower(), Path(root) / name
                if key in index:
                    raise ValueError(
                        f"duplicate audio id {key!r}: {index[key]} and {path}"
                    )
                index[key] = path
    return index


if __name__ == "__main__":
    out = download()
    print(f"Corpus ready at {out}")
    print(f"Loaded {len(load_scores(out))} utterances")
