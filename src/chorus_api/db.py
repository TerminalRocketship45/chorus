"""SQLite storage (stdlib sqlite3 only), per docs/api.md's student and session shapes.

Recordings are never stored — only each session's score, accent-adjusted
score, per-word results (as JSON), practice words and accent_ok_count.

Path comes from env CHORUS_DB (default "./chorus.db"). A fresh connection is
opened per call: sqlite3 connections are not safe to share across threads by
default, and chorus_api/app.py runs the analysis itself in a worker thread,
so the simplest correct thing is "no shared connection, no shared state".
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    grade_band TEXT NOT NULL,
    home_language TEXT,
    created_at TEXT NOT NULL,
    interests TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id),
    passage_id TEXT NOT NULL,
    passage_title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    home_language TEXT,
    score_json TEXT NOT NULL,
    accent_adjusted_json TEXT,
    words_json TEXT NOT NULL,
    practice_words_json TEXT NOT NULL,
    accent_ok_count INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_student_id ON sessions(student_id);

CREATE TABLE IF NOT EXISTS generated_passages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    band TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 2,
    topic TEXT NOT NULL,
    text TEXT NOT NULL,
    student_id INTEGER REFERENCES students(id),
    created_at TEXT NOT NULL
);
"""


def db_path() -> str:
    return os.environ.get("CHORUS_DB", "./chorus.db")


@contextmanager
def _connect(path: str | None = None) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: str | None = None) -> None:
    """Create the tables if they do not exist yet. Safe to call repeatedly."""
    with _connect(path) as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring a database created by an older version up to the current schema."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(students)")}
    if "interests" not in cols:
        conn.execute("ALTER TABLE students ADD COLUMN interests TEXT NOT NULL DEFAULT '[]'")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Students
# --------------------------------------------------------------------------


_STUDENT_COLS = "id, name, grade_band, home_language, created_at, interests"


def _student_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["interests"] = json.loads(d["interests"]) if d.get("interests") else []
    return d


def create_student(
    name: str,
    grade_band: str,
    home_language: str | None,
    path: str | None = None,
    interests: list[str] | None = None,
) -> dict[str, Any]:
    created_at = _now_iso()
    interests = list(interests or [])
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO students (name, grade_band, home_language, created_at, interests) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, grade_band, home_language, created_at, json.dumps(interests)),
        )
        student_id = cur.lastrowid
    return {
        "id": student_id,
        "name": name,
        "grade_band": grade_band,
        "home_language": home_language,
        "created_at": created_at,
        "interests": interests,
    }


def get_student(student_id: int, path: str | None = None) -> dict[str, Any] | None:
    with _connect(path) as conn:
        row = conn.execute(
            f"SELECT {_STUDENT_COLS} FROM students WHERE id = ?", (student_id,)
        ).fetchone()
    return _student_row_to_dict(row) if row else None


_UPDATABLE = ("name", "grade_band", "home_language", "interests")


def update_student(
    student_id: int, fields: dict[str, Any], path: str | None = None
) -> dict[str, Any] | None:
    """Set the given fields (a subset of name/grade_band/home_language/interests).

    Returns the updated student, or None when the id does not exist. The
    caller validates values.
    """
    sets, vals = [], []
    for key in _UPDATABLE:
        if key in fields:
            sets.append(f"{key} = ?")
            vals.append(json.dumps(fields[key]) if key == "interests" else fields[key])
    with _connect(path) as conn:
        if sets:
            conn.execute(
                f"UPDATE students SET {', '.join(sets)} WHERE id = ?", (*vals, student_id)
            )
    return get_student(student_id, path)


def list_students(path: str | None = None) -> list[dict[str, Any]]:
    """Every student plus session_count, last_session_at (or None) and last_wcpm (or None)."""
    with _connect(path) as conn:
        rows = conn.execute(
            f"SELECT {_STUDENT_COLS} FROM students ORDER BY id"
        ).fetchall()
        out = []
        for row in rows:
            student = _student_row_to_dict(row)
            sess = conn.execute(
                "SELECT score_json, created_at FROM sessions "
                "WHERE student_id = ? ORDER BY id DESC LIMIT 1",
                (student["id"],),
            ).fetchone()
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM sessions WHERE student_id = ?",
                (student["id"],),
            ).fetchone()["n"]
            student["session_count"] = count
            if sess is not None:
                student["last_session_at"] = sess["created_at"]
                student["last_wcpm"] = json.loads(sess["score_json"])["wcpm"]
            else:
                student["last_session_at"] = None
                student["last_wcpm"] = None
            out.append(student)
    return out


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------


def create_session(
    student_id: int,
    passage_id: str,
    passage_title: str,
    home_language: str | None,
    score: dict[str, Any],
    accent_adjusted: dict[str, Any] | None,
    words: list[dict[str, Any]],
    practice_words: list[str],
    accent_ok_count: int,
    path: str | None = None,
) -> dict[str, Any]:
    created_at = _now_iso()
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO sessions ("
            "  student_id, passage_id, passage_title, created_at, home_language,"
            "  score_json, accent_adjusted_json, words_json, practice_words_json,"
            "  accent_ok_count"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                student_id,
                passage_id,
                passage_title,
                created_at,
                home_language,
                json.dumps(score),
                json.dumps(accent_adjusted) if accent_adjusted is not None else None,
                json.dumps(words),
                json.dumps(practice_words),
                accent_ok_count,
            ),
        )
        session_id = cur.lastrowid
    return {"id": session_id, "created_at": created_at}


def _session_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "passage_id": row["passage_id"],
        "passage_title": row["passage_title"],
        "created_at": row["created_at"],
        "score": json.loads(row["score_json"]),
        "accent_adjusted": (
            json.loads(row["accent_adjusted_json"])
            if row["accent_adjusted_json"] is not None
            else None
        ),
        "accent_ok_count": row["accent_ok_count"],
        "practice_words": json.loads(row["practice_words_json"]),
    }


def list_sessions(student_id: int, path: str | None = None) -> list[dict[str, Any]]:
    """Sessions for one student, oldest first (for the trend line)."""
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT id, passage_id, passage_title, created_at, score_json,"
            " accent_adjusted_json, words_json, practice_words_json, accent_ok_count"
            " FROM sessions WHERE student_id = ? ORDER BY id ASC",
            (student_id,),
        ).fetchall()
    return [_session_row_to_dict(r) for r in rows]


def most_missed(
    student_id: int, path: str | None = None, top: int = 10
) -> list[dict[str, Any]]:
    """Top `misread`/`skipped` words across all of this student's sessions.

    `words_json` holds the full per-word API dicts (each with a `display`
    field), so this counts `display in {"misread", "skipped"}` occurrences of
    each `expected` word, across every saved session. Ties break alphabetically
    for a deterministic order.
    """
    counts: dict[str, int] = {}
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT words_json FROM sessions WHERE student_id = ?", (student_id,)
        ).fetchall()
    for row in rows:
        for w in json.loads(row["words_json"]):
            if w.get("display") in ("misread", "skipped"):
                counts[w["expected"]] = counts.get(w["expected"], 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"word": word, "count": count} for word, count in ranked[:top]]


# --------------------------------------------------------------------------
# AI-written passages
# --------------------------------------------------------------------------


def _generated_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": f"g-{row['id']}",
        "title": row["title"],
        "band": row["band"],
        "level": row["level"],
        "topic": row["topic"],
        "text": row["text"],
        "student_id": row["student_id"],
        "created_at": row["created_at"],
    }


def create_generated_passage(
    title: str,
    band: str,
    topic: str,
    text: str,
    level: int = 2,
    student_id: int | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    with _connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO generated_passages (title, band, level, topic, text, student_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, band, level, topic, text, student_id, _now_iso()),
        )
        row = conn.execute(
            "SELECT * FROM generated_passages WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _generated_row_to_dict(row)


def get_generated_passage(passage_id: str, path: str | None = None) -> dict[str, Any] | None:
    """Resolve a "g-<n>" id; None for a malformed or unknown id."""
    if not passage_id.startswith("g-") or not passage_id[2:].isascii() or not passage_id[2:].isdigit():
        return None
    with _connect(path) as conn:
        try:
            row = conn.execute(
                "SELECT * FROM generated_passages WHERE id = ?", (int(passage_id[2:]),)
            ).fetchone()
        except sqlite3.OperationalError:  # table not created yet
            return None
    return _generated_row_to_dict(row) if row else None


def list_generated_for_student(student_id: int, path: str | None = None) -> list[dict[str, Any]]:
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM generated_passages WHERE student_id = ? ORDER BY id", (student_id,)
        ).fetchall()
    return [_generated_row_to_dict(r) for r in rows]


def passage_session_stats(student_id: int, path: str | None = None) -> dict[str, dict[str, Any]]:
    """passage_id -> {attempts, last_session_id, at, score, accent_adjusted} (newest session)."""
    stats: dict[str, dict[str, Any]] = {}
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT id, passage_id, created_at, score_json, accent_adjusted_json "
            "FROM sessions WHERE student_id = ? ORDER BY id ASC",
            (student_id,),
        ).fetchall()
    for r in rows:  # oldest first, so the last write per passage is the newest
        prev = stats.get(r["passage_id"])
        stats[r["passage_id"]] = {
            "attempts": (prev["attempts"] if prev else 0) + 1,
            "last_session_id": r["id"],
            "at": r["created_at"],
            "score": json.loads(r["score_json"]),
            "accent_adjusted": (
                json.loads(r["accent_adjusted_json"]) if r["accent_adjusted_json"] else None
            ),
        }
    return stats
