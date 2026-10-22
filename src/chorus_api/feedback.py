"""POST /api/feedback: a short, warm comment on one reading.

The model gets a compact structured summary (never raw accent differences or
"extra word nearby" markers as errors). Its reply is checked against hard rules;
anything that breaks them, a missing token, or any provider error gives a
deterministic template comment instead (source "template").

Same Hugging Face InferenceClient setup as generate.py (env HF_TOKEN); the model
is CHORUS_FEEDBACK_MODEL, else CHORUS_PASSAGE_MODEL, else generate.DEFAULT_MODEL.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from . import generate

log = logging.getLogger("chorus_api.feedback")

ATTEMPTS = 2
MAX_TOKENS = 200
MAX_WORDS = 70
MAX_PRACTICE = 3

#: Fragments that must never appear in a comment (lowercase substring match).
FORBIDDEN = ("accent", "disorder", "dyslexi", "diagnos", "impair", "disabilit", "condition")


def _model() -> str:
    return os.environ.get("CHORUS_FEEDBACK_MODEL") or generate._model()


def _num(d: dict | None, key: str, default: float = 0.0) -> float:
    try:
        return float((d or {}).get(key, default))
    except (TypeError, ValueError):
        return default


def summarize(
    words: list[dict[str, Any]], score: dict[str, Any], accent_adjusted: dict[str, Any] | None
) -> dict[str, Any]:
    """Structured facts for the comment. Misread = substitution (not accent-excused,
    not accent_ok) with what was heard; skipped = omission. extra_nearby words and
    accent-excused words are never listed as errors."""
    misread: list[dict[str, str]] = []
    skipped: list[str] = []
    repeated = self_corrected = 0
    for w in words:
        if not isinstance(w, dict):
            continue
        status = w.get("status")
        display = w.get("display")
        if w.get("accent_excused") or display in ("accent_ok", "extra_nearby"):
            continue
        expected = str(w.get("expected") or "").strip()
        if not expected:
            continue
        if status == "substitution":
            misread.append({"word": expected, "heard": str(w.get("heard") or "")})
        elif status == "omission":
            skipped.append(expected)
        elif status == "repetition":
            repeated += 1
        elif status == "self_correction":
            self_corrected += 1
    out: dict[str, Any] = {
        "words_correct_per_minute": round(_num(score, "wcpm")),
        "accuracy_percent": round(_num(score, "accuracy") * 100),
        "misread_words": misread,
        "skipped_words": skipped,
        "repeated_count": repeated,
        "self_corrected_count": self_corrected,
    }
    if accent_adjusted:
        out["accuracy_percent_accent_adjusted"] = round(_num(accent_adjusted, "accuracy") * 100)
    return out


def practice_set(summary: dict[str, Any]) -> list[str]:
    """Distinct misread/skipped words, misread first, in passage order."""
    seen: list[str] = []
    for w in [m["word"] for m in summary["misread_words"]] + summary["skipped_words"]:
        if w.lower() not in (x.lower() for x in seen):
            seen.append(w)
    return seen


def build_messages(summary: dict[str, Any], band_hint: str | None = None) -> list[dict[str, str]]:
    system = (
        "You are a kind reading coach talking directly to a child who just read aloud. "
        "Reply with plain text only."
    )
    lines = [
        f"Reading speed: about {summary['words_correct_per_minute']} words correct per minute.",
        f"Accuracy: {summary['accuracy_percent']} percent.",
    ]
    if "accuracy_percent_accent_adjusted" in summary:
        lines.append(
            f"Accuracy when pronunciation differences are set aside: "
            f"{summary['accuracy_percent_accent_adjusted']} percent."
        )
    if summary["misread_words"]:
        lines.append(
            "Words misread (word, what was heard): "
            + "; ".join(f"{m['word']} -> {m['heard'] or '?'}" for m in summary["misread_words"][:8])
        )
    if summary["skipped_words"]:
        lines.append("Words skipped: " + ", ".join(summary["skipped_words"][:8]))
    if summary["repeated_count"] or summary["self_corrected_count"]:
        lines.append(
            f"Repeated words: {summary['repeated_count']}. "
            f"Words the reader fixed by themselves: {summary['self_corrected_count']}."
        )
    user = (
        "\n".join(lines)
        + "\n\nWrite 2 to 4 short sentences, at most 70 words in total, speaking to the reader "
        'as "you". Be encouraging and specific. Say the reading speed in plain words '
        '("words correct per minute"). Suggest practicing at most three words, and only words '
        "from the misread or skipped lists. Do not mention accents, do not diagnose or label "
        "the reader, and do not list every error."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


_CUE = re.compile(r"\b(?:practi[cs]ing|practi[cs]e|try|work on|focus on|review)\b", re.I)


def validate_reply(text: str, summary: dict[str, Any], vocab: set[str] | None = None) -> str | None:
    """The cleaned reply, or None when it breaks a rule: 2 to 4 sentences, at most 70
    words, no forbidden term, and no practice word outside the misread/skipped set.

    A "practice word" is any passage word (`vocab`, longer than 3 letters) or quoted
    word named after a practice cue ("practice", "try", "work on", ...)."""
    if not isinstance(text, str):
        return None
    t = re.sub(r"\s+", " ", generate.clean_text(text)).strip().strip('"').strip()
    if not t or len(t.split()) > MAX_WORDS:
        return None
    sentences = [x for x in re.split(r"(?<=[.!?])\s+", t) if x.strip()]
    if not 2 <= len(sentences) <= 4:
        return None
    low = t.lower()
    if any(f in low for f in FORBIDDEN):
        return None
    allowed = {w.lower() for w in practice_set(summary)}
    for sent in sentences:
        m = _CUE.search(sent)
        if not m:
            continue
        tail = sent[m.end():]
        named = {x.lower() for x in re.findall(r"[A-Za-z']+", tail)}
        quoted = {q.lower() for q in re.findall(r"[\"'\u201c]([A-Za-z]+)[\"'\u201d]", tail)}
        listed: set[str] = set()
        if ":" in tail:  # "Try practicing: a, b and c." -> every listed single word counts
            items = re.split(r",|\band\b", tail.split(":", 1)[1].strip().rstrip(".!"))
            listed = {i.strip().lower() for i in items if re.fullmatch(r"[A-Za-z']+", i.strip())}
        for w in quoted | listed | {x for x in named & (vocab or set()) if len(x) > 3}:
            if w not in allowed:
                return None
    return t


def template(summary: dict[str, Any]) -> str:
    wcpm = summary["words_correct_per_minute"]
    first = f"You read at about {wcpm} words correct per minute."
    practice = practice_set(summary)[:MAX_PRACTICE]
    if summary["accuracy_percent"] >= 90:
        second = "Great work, you read almost every word just right."
    elif summary["self_corrected_count"]:
        second = "Nice work fixing words by yourself as you went."
    else:
        second = "Nice work staying with the whole passage."
    if practice:
        third = "Try practicing: " + ", ".join(practice) + "."
    else:
        third = "Keep reading a little every day and it will keep getting easier."
    return f"{first} {second} {third}"


def make_feedback(
    words: list[dict[str, Any]],
    score: dict[str, Any],
    accent_adjusted: dict[str, Any] | None = None,
    home_language: str | None = None,
) -> dict[str, str]:
    """Blocking; call via asyncio.to_thread. Never raises for provider trouble."""
    summary = summarize(words, score, accent_adjusted)
    vocab = {str(w.get("expected", "")).lower() for w in words if isinstance(w, dict)}
    token = os.environ.get("HF_TOKEN")
    if token:
        try:
            client = generate._make_client(token, _model())
        except Exception as exc:
            log.warning("feedback unavailable: %s", exc)
            client = None
        for attempt in range(ATTEMPTS if client else 0):
            try:
                resp = client.chat_completion(
                    messages=build_messages(summary), max_tokens=MAX_TOKENS, temperature=0.6
                )
                reply = validate_reply(resp.choices[0].message.content, summary, vocab)
            except Exception as exc:
                log.warning("feedback attempt %d failed: %s", attempt + 1, type(exc).__name__)
                if generate._fatal(exc):
                    break
                continue
            if reply:
                return {"feedback": reply, "source": "ai"}
            log.info("feedback attempt %d broke the rules", attempt + 1)
    return {"feedback": template(summary), "source": "template"}
