"""AI-written reading passages (POST /api/passages/generate).

Provider: Hugging Face Inference Providers via
`huggingface_hub.InferenceClient(...).chat_completion(...)`. The token comes
from env HF_TOKEN (a fine-grained token with the "Make calls to Inference
Providers" permission, or a read token) and the model id from env
CHORUS_PASSAGE_MODEL.

Every model reply is checked by `validate_passage` (the engine's limits: words
only, plain ASCII, aligner-friendly tokens, the band's length range, nothing
unsafe). After `ATTEMPTS` failed tries, or with no token, or on any provider
error such as no credit, a library passage is returned instead, so a reader is
never left without something to read.
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
from dataclasses import asdict
from typing import Any

from chorus.miscue import normalize

from . import db
from . import interests as interests_mod
from . import passages as passages_mod

log = logging.getLogger("chorus_api.generate")

#: Llama 3.1 8B Instruct: ~8B, and served "live" by several Inference Providers
#: (novita, nscale, featherless-ai, deepinfra) that free HF accounts can use
#: with their monthly credit. Override with env CHORUS_PASSAGE_MODEL.
DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
ATTEMPTS = 3
TIMEOUT_S = 20.0
MAX_TOKENS = 450
DEFAULT_LEVEL = 2

WORD_RANGE = {"elementary": (40, 80), "secondary": (80, 130)}
_GRADES = {"elementary": "grades 2 to 5", "secondary": "grades 6 to 12"}
MAX_TITLE_WORDS = 8

#: Same rule as chorus.pipeline._is_alignable: the aligner only times [a-z']
#: tokens with at least one letter.
_ALIGNABLE = re.compile(r"[a-z']*[a-z][a-z']*")

#: Small blocklist (whole words, lowercase). Not a substitute for the prompt's
#: rules; a cheap last check on the model's output.
_BLOCKLIST = frozenset(
    """
    kill kills killed killing murder murdered blood bloody gun guns shoot shot shooting
    knife knives weapon weapons bomb bombs war wars terror terrorist die dies died dying
    death suicide corpse ghost ghosts demon demons devil hell damn drug drugs alcohol
    beer wine vodka cigarette cigarettes smoking sex sexy kiss kissed kissing boyfriend
    girlfriend dating naked stupid idiot hate hated hates god jesus allah church mosque
    temple pray prayer election president democrat republican trump biden abuse rape
    """.split()
)

_CHAR_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "—": ", ", "–": ", ", "―": ", ",
    "…": "...", " ": " ",
}
_CHAR_RE = re.compile("|".join(map(re.escape, _CHAR_MAP)))


def clean_text(s: str) -> str:
    """Curly quotes and dashes to ASCII, and whitespace runs to single spaces."""
    s = _CHAR_RE.sub(lambda m: _CHAR_MAP[m.group(0)], s)
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\s+,", ",", s)


def validate_passage(text: str, band: str, title: str | None = None) -> list[str]:
    """Problems that make `text` (and optionally `title`) unusable; [] means fine.

    Pass text already run through `clean_text`; anything left non-ASCII is a problem.
    """
    problems: list[str] = []
    if band not in WORD_RANGE:
        return [f"unknown band: {band!r}"]
    if not isinstance(text, str) or not text.strip():
        return ["text is empty"]
    if any(ch.isdigit() for ch in text):
        problems.append("contains digits")
    if "-" in text:
        problems.append("contains a hyphen")
    if any(ord(ch) > 127 for ch in text):
        problems.append("contains non-ASCII characters")
    tokens = normalize(text)
    bad = sorted({t for t in tokens if not _ALIGNABLE.fullmatch(t)})
    if bad:
        problems.append(f"unalignable tokens: {bad[:5]}")
    lo, hi = WORD_RANGE[band]
    if not lo <= len(tokens) <= hi:
        problems.append(f"{len(tokens)} words, need {lo} to {hi}")
    unsafe = sorted({t for t in tokens if t.strip("'") in _BLOCKLIST})
    if unsafe:
        problems.append(f"unsafe words: {unsafe}")
    if title is not None:
        t = title.strip() if isinstance(title, str) else ""
        if not t:
            problems.append("title is empty")
        else:
            if len(t.split()) > MAX_TITLE_WORDS:
                problems.append(f"title longer than {MAX_TITLE_WORDS} words")
            if any(ch.isdigit() for ch in t) or "-" in t or any(ord(ch) > 127 for ch in t):
                problems.append("title has digits, hyphens or non-ASCII characters")
            if any(w.strip("'").lower() in _BLOCKLIST for w in re.findall(r"[A-Za-z']+", t)):
                problems.append("title has unsafe words")
    return problems


_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def parse_response(raw: str) -> tuple[str, str]:
    """Pull (title, text) out of a model reply: JSON, possibly code-fenced or with
    chatter around it. Both strings are returned cleaned. Raises ValueError."""
    if not isinstance(raw, str):
        raise ValueError("reply is not text")
    s = raw.strip()
    s = _FENCE.sub("", s).strip()
    obj: Any = None
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        a, b = s.find("{"), s.rfind("}")
        if a != -1 and b > a:
            try:
                obj = json.loads(s[a : b + 1])
            except json.JSONDecodeError:
                pass
    if not isinstance(obj, dict) or not isinstance(obj.get("title"), str) or not isinstance(
        obj.get("text"), str
    ):
        raise ValueError("reply is not JSON with string title and text")
    return clean_text(obj["title"]), clean_text(obj["text"])


def build_prompt(band: str, interest_label: str) -> list[dict[str, str]]:
    lo, hi = WORD_RANGE[band]
    system = (
        "You write short original reading passages for students to read aloud. "
        "You reply with JSON only."
    )
    user = (
        f"Write ONE original reading passage for students in {_GRADES[band]} about "
        f"{interest_label.lower()}. It must be between {lo} and {hi} words long. "
        'Reply with only this JSON: {"title": "...", "text": "..."}. The title has at '
        "most six words.\n"
        "Rules:\n"
        "- Use words only. Write numbers as words, never digits.\n"
        "- No hyphenated words. Do not use hyphens at all.\n"
        "- No em dashes, no curly quotes. Use plain ASCII punctuation.\n"
        "- Do not name any real living person, and do not mention brands.\n"
        "- Nothing scary, violent, romantic, political or religious.\n"
        "- Warm, concrete and age appropriate, with clear sentences a child can read aloud."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _model() -> str:
    return os.environ.get("CHORUS_PASSAGE_MODEL") or DEFAULT_MODEL


def _make_client(token: str, model: str):
    from huggingface_hub import InferenceClient

    return InferenceClient(model=model, token=token, timeout=TIMEOUT_S)


def _call_model(client, band: str, interest: str) -> str:
    label = next(i["label"] for i in interests_mod.INTERESTS if i["code"] == interest)
    resp = client.chat_completion(
        messages=build_prompt(band, label), max_tokens=MAX_TOKENS, temperature=0.8
    )
    return resp.choices[0].message.content


def _fatal(exc: Exception) -> bool:
    """Errors a retry cannot fix: bad or unauthorised token, no credit, unknown model."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status in (401, 402, 403, 404)


def library_fallback(
    band: str, interests: list[str], exclude_ids: list[str]
) -> dict[str, Any]:
    """A library passage: band match, interest match if possible, not excluded."""
    pool = [p for p in passages_mod.list_passages(band) if p.id not in exclude_ids]
    if not pool:  # everything excluded: repeating beats returning nothing
        pool = passages_mod.list_passages(band)
    matching = [p for p in pool if p.topic in interests]
    return asdict(random.choice(matching or pool))


def generate_passage(
    band: str,
    interests: list[str] | None = None,
    student_id: int | None = None,
    exclude_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Blocking; call via asyncio.to_thread. Returns a passage dict (source "ai"
    after a stored generation, "library" for the fallback). Never raises for
    provider trouble."""
    interests = list(interests or []) or interests_mod.ordered_codes()
    exclude_ids = list(exclude_ids or [])
    token = os.environ.get("HF_TOKEN")
    if token:
        interest = random.choice(interests)
        try:
            client = _make_client(token, _model())
        except Exception as exc:  # e.g. huggingface_hub missing
            log.warning("passage generation unavailable: %s", exc)
            client = None
        for attempt in range(ATTEMPTS if client else 0):
            try:
                title, text = parse_response(_call_model(client, band, interest))
            except ValueError as exc:
                log.info("attempt %d: unusable reply: %s", attempt + 1, exc)
                continue
            except Exception as exc:
                log.warning("attempt %d: model call failed: %s", attempt + 1, type(exc).__name__)
                if _fatal(exc):
                    break
                continue
            problems = validate_passage(text, band, title)
            if problems:
                log.info("attempt %d rejected: %s", attempt + 1, problems)
                continue
            row = db.create_generated_passage(
                title=title,
                band=band,
                topic=interest,
                text=text,
                level=DEFAULT_LEVEL,
                student_id=student_id,
            )
            return asdict(passages_mod.from_generated(row))
    return library_fallback(band, interests, exclude_ids)
