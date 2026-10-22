"""GET /api/interests: the fixed interest list for onboarding, in display order.

Interest codes are stored on students and used as the `topic` of passages
(library passages are tagged with these codes; AI-written passages use the
interest they were written about).
"""
from __future__ import annotations

from typing import TypedDict


class Interest(TypedDict):
    code: str
    label: str


#: Exact order and content from docs/api.md.
INTERESTS: list[Interest] = [
    {"code": "animals", "label": "Animals"},
    {"code": "sports", "label": "Sports"},
    {"code": "space", "label": "Space"},
    {"code": "nature", "label": "Nature"},
    {"code": "food", "label": "Food"},
    {"code": "music", "label": "Music"},
    {"code": "art", "label": "Art"},
    {"code": "science", "label": "Science"},
    {"code": "history", "label": "History"},
    {"code": "adventure", "label": "Adventure"},
]

_CODES = tuple(i["code"] for i in INTERESTS)


def known_codes() -> frozenset[str]:
    return frozenset(_CODES)


def ordered_codes() -> list[str]:
    return list(_CODES)


def list_interests() -> list[Interest]:
    return list(INTERESTS)


def normalize_codes(value: object) -> list[str]:
    """Validate a client-supplied interests value; return it de-duplicated, order kept.

    Raises ValueError for a non-list, a non-string item or an unknown code.
    """
    if not isinstance(value, list):
        raise ValueError("interests must be a list of interest codes")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or item not in _CODES:
            raise ValueError(f"unknown interest: {item!r}")
        if item not in out:
            out.append(item)
    return out
