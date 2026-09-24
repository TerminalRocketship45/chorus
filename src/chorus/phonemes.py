"""Grapheme-to-phoneme conversion.

Uses g2p_en (CMUdict plus a neural fallback for out-of-vocabulary words) and
emits stress-free ARPAbet, which is what the L1 rule sets are written against.
"""
from __future__ import annotations

from functools import lru_cache

_g2p = None


def _get_g2p():
    """Lazily construct the G2p object; it loads data files on first use."""
    global _g2p
    if _g2p is None:
        from g2p_en import G2p

        _g2p = G2p()
    return _g2p


def strip_stress(symbol: str) -> str:
    """Remove ARPAbet stress digits: 'AA1' -> 'AA'."""
    return "".join(c for c in symbol if not c.isdigit())


@lru_cache(maxsize=8192)
def to_phonemes(word: str) -> tuple[str, ...]:
    """Convert a single word to stress-free ARPAbet symbols.

    Cached because passages repeat words heavily. Returns a tuple so the
    cache stays safe; callers treat it as a sequence.
    """
    word = word.strip().lower()
    if not word:
        return ()
    raw = _get_g2p()(word)
    return tuple(
        strip_stress(p) for p in raw if p.isalnum() and not p.isspace()
    )
