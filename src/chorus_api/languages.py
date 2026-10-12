"""GET /api/languages: home languages for onboarding, in display order.

`support` meanings (must be stated honestly by the UI, per docs/api.md):
  measured:   accent rules checked against expert labels (Mandarin only).
  rules:      accent rules from published research, not yet measured.
  not_yet:    no accent rules yet; scored without accent adjustment.
  not_needed: no accent adjustment applied.

Only `measured` and `rules` codes are passed to chorus.pipeline.analyze as
`language` (they are the codes that have a chorus.l1 rule file). `not_yet`
and `not_needed` codes are never passed to the engine.
"""
from __future__ import annotations

from typing import TypedDict


class Language(TypedDict):
    code: str
    label: str
    support: str


#: Exact order and content from docs/api.md (Somali first: the featured language).
LANGUAGES: list[Language] = [
    {"code": "somali", "label": "Somali", "support": "rules"},
    {"code": "spanish", "label": "Spanish", "support": "rules"},
    {"code": "mandarin", "label": "Mandarin Chinese", "support": "measured"},
    {"code": "hmong", "label": "Hmong", "support": "not_yet"},
    {"code": "karen", "label": "Karen", "support": "not_yet"},
    {"code": "english", "label": "English only", "support": "not_needed"},
    {"code": "other", "label": "Another language", "support": "not_yet"},
]

#: code -> Language, for O(1) lookups.
_BY_CODE: dict[str, Language] = {lang["code"]: lang for lang in LANGUAGES}

#: Support levels for which a code is forwarded to the engine as `language`.
_ENGINE_SUPPORT = frozenset({"measured", "rules"})


def known_codes() -> frozenset[str]:
    """All valid `home_language` codes."""
    return frozenset(_BY_CODE)


def engine_language(code: str | None) -> str | None:
    """The `language` to pass to chorus.pipeline.analyze, or None.

    None in, None out. A code with support `not_yet`/`not_needed` also
    yields None: the engine has no rules for it. Only `measured`/`rules`
    codes (which is to say, only codes with a chorus.l1 rule file) pass
    through unchanged. Raises KeyError for an unknown code.
    """
    if code is None:
        return None
    lang = _BY_CODE[code]
    return code if lang["support"] in _ENGINE_SUPPORT else None


def list_languages() -> list[Language]:
    return list(LANGUAGES)
