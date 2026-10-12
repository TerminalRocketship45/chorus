"""Loads the bundled reading passages (data files, no copyrighted text).

GET /api/passages?band=elementary|secondary (docs/api.md). `word_count` is
never stored in the data files; it is computed at load time with
`chorus.miscue.normalize`, the same tokenizer the engine scores against, so
the count a client sees always matches what the engine will actually time.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from chorus.miscue import normalize

_DATA_DIR = Path(__file__).parent / "passages"
BANDS = frozenset({"elementary", "secondary"})


@dataclass(frozen=True)
class Passage:
    id: str
    title: str
    band: str
    level: int
    topic: str
    text: str
    word_count: int


def _load_file(path: Path) -> list[Passage]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        Passage(
            id=p["id"],
            title=p["title"],
            band=p["band"],
            level=p["level"],
            topic=p["topic"],
            text=p["text"],
            word_count=len(normalize(p["text"])),
        )
        for p in raw
    ]


@lru_cache(maxsize=1)
def load_passages() -> tuple[Passage, ...]:
    """All bundled passages (both bands), loaded and tokenised once per process."""
    passages: list[Passage] = []
    for fname in ("elementary.json", "secondary.json"):
        passages.extend(_load_file(_DATA_DIR / fname))
    return tuple(passages)


def list_passages(band: str | None = None) -> list[Passage]:
    """Passages, optionally filtered to one band.

    Raises ValueError for a `band` that is not "elementary" or "secondary";
    the caller (app.py) turns that into a 400.
    """
    if band is not None and band not in BANDS:
        raise ValueError(f"unknown band: {band!r}")
    passages = load_passages()
    if band is None:
        return list(passages)
    return [p for p in passages if p.band == band]


def get_passage(passage_id: str) -> Passage | None:
    """One passage by id, or None if it does not exist."""
    for p in load_passages():
        if p.id == passage_id:
            return p
    return None
