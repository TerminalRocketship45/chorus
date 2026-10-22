"""The Chorus FastAPI service: wraps chorus.pipeline.analyze() per docs/api.md.

`create_app()` is the factory; `app` (module level) is the instance uvicorn
serves (`uvicorn chorus_api.app:app`).
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import time
import shutil
import tempfile
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from chorus import pipeline
from chorus.types import WordResult, WordStatus

from . import db
from . import display as display_mod
from . import generate as generate_mod
from . import interests as interests_mod
from . import languages as languages_mod
from . import passages as passages_mod
from . import feedback as feedback_mod
from .audio import (
    SILENT_PEAK_DBFS,
    AudioTooLong,
    UndecodableAudio,
    decode_to_wav,
    normalize_wav_peak,
    wav_levels,
)
from .concurrency import AnalysisBusy, AnalysisGate

#: repo_root/web/dist — the built React app, if it exists (another agent owns web/).
WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_DURATION_S = 120.0
NO_SPEECH_MESSAGE = (
    "Chorus couldn't hear enough reading. Check the microphone, move closer, and try again."
)
TOO_QUIET_MESSAGE = (
    "Your recording was very quiet. Check the microphone, move closer, and try again."
)
#: A reading is rejected as "not heard" when fewer than this share of the passage's
#: words were heard as correct or close (see `_heard_fraction`). A struggling reader
#: still matches far more than this; text Whisper invents from silence matches ~none.
MIN_HEARD_FRACTION = 0.15
#: A substituted word counts as "close" when its spelling is at least this similar.
NEAR_RATIO = 0.6

log = logging.getLogger("chorus_api.app")

#: Serialises chorus.pipeline.analyze calls to one at a time, 3-deep wait queue.
_gate = AnalysisGate(max_queue=3)


def _model_size() -> str:
    return os.environ.get("CHORUS_ASR_MODEL", "small.en")


def _env_flag(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None or not v.strip():
        return default
    return v.strip().lower() not in ("0", "false", "no", "off")


def _env_beam_size() -> int:
    try:
        return max(1, int(os.environ.get("CHORUS_BEAM_SIZE", "5")))
    except ValueError:
        return 5


def _analysis_options() -> dict[str, Any]:
    """Recogniser options, read at request time. Measured best setting by default
    (see SETUP.md). prompt_passage is deliberately not exposed: it hides genuine errors."""
    return {
        "beam_size": _env_beam_size(),
        "same_sound": _env_flag("CHORUS_SAME_SOUND", True),
        "digit_context": _env_flag("CHORUS_DIGIT_CONTEXT", True),
        "vad_filter": _env_flag("CHORUS_VAD", VAD_DEFAULT),
        "drop_hallucinations": _env_flag("CHORUS_DROP_HALLUCINATIONS", True),
    }


#: Voice-activity filtering before decoding; see SETUP.md for the measurement.
VAD_DEFAULT = True


def _debug_dir() -> Path | None:
    """CHORUS_DEBUG_AUDIO_DIR: a debugging aid only. Unset (default) means audio is never stored."""
    v = os.environ.get("CHORUS_DEBUG_AUDIO_DIR")
    return Path(v) if v and v.strip() else None


def _save_debug(raw_path: str, wav_path: str, meta: dict[str, Any]) -> None:
    d = _debug_dir()
    if d is None:
        return
    try:
        d.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
        stem = f"{stamp}_{meta.get('passage_id', 'unknown')}"
        if os.path.exists(raw_path):
            shutil.copyfile(raw_path, d / f"{stem}.upload")
        if os.path.exists(wav_path):
            shutil.copyfile(wav_path, d / f"{stem}.wav")
        (d / f"{stem}.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    except Exception as exc:  # never let debugging break a request
        log.warning("debug audio capture failed: %s", exc)


def _heard_fraction(words: list[WordResult]) -> float:
    """Share of the passage's words heard as correct or close.

    A word counts when what was heard equals what was expected, or is a close
    spelling of it (difflib ratio >= NEAR_RATIO, e.g. kat/cat). Omissions and
    unrelated words do not count.
    """
    if not words:
        return 0.0
    ok = 0
    for w in words:
        if w.heard is None:
            continue
        if w.heard == w.expected or (
            difflib.SequenceMatcher(None, w.heard, w.expected).ratio() >= NEAR_RATIO
        ):
            ok += 1
    return ok / len(words)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    db.init_db()
    if os.environ.get("CHORUS_WARMUP") == "1":
        # Load the Whisper and aligner models now so the first real request
        # isn't the one that pays for it. One at a time, in this one process.
        from chorus.align import _get_model_bundle
        from chorus.asr import _get_model

        await asyncio.to_thread(_get_model, _model_size())
        await asyncio.to_thread(_get_model_bundle)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Chorus API", lifespan=_lifespan)
    _add_routes(app)
    _add_static(app)
    return app


def _word_to_dict(w: WordResult) -> dict[str, Any]:
    return {
        "index": w.index,
        "expected": w.expected,
        "heard": w.heard,
        "status": w.status.value,
        "accent_excused": w.accent_excused,
        "display": display_mod.word_display(w),
        "start": w.start,
        "end": w.end,
    }


def _parse_interests(value: Any) -> list[str]:
    try:
        return interests_mod.normalize_codes(value)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


def _student_passages(student_id: int) -> list[dict[str, Any]]:
    """Passages this student generated or read, newest first, with read marks."""
    stats = db.passage_session_stats(student_id)
    items: list[tuple[tuple[str, int], dict[str, Any]]] = []
    seen: set[str] = set()
    for row in db.list_generated_for_student(student_id):
        pid = row["id"]
        seen.add(pid)
        st = stats.get(pid)
        key = (max(row["created_at"], st["at"]) if st else row["created_at"],
               st["last_session_id"] if st else int(pid[2:]))
        items.append((key, _passage_entry(passages_mod.from_generated(row), st)))
    for pid, st in stats.items():
        if pid in seen:
            continue
        passage = passages_mod.get_passage(pid)
        if passage is None:
            continue
        items.append(((st["at"], st["last_session_id"]), _passage_entry(passage, st)))
    items.sort(key=lambda kv: kv[0], reverse=True)
    return [entry for _, entry in items]


def _passage_entry(passage: Any, st: dict[str, Any] | None) -> dict[str, Any]:
    last = None
    if st:
        adj = st["accent_adjusted"]
        last = {
            "accuracy": st["score"]["accuracy"],
            "accent_adjusted_accuracy": adj["accuracy"] if adj else None,
            "wcpm": st["score"]["wcpm"],
            "at": st["at"],
        }
    return {
        "passage": asdict(passage),
        "read": st is not None,
        "attempts": st["attempts"] if st else 0,
        "last_result": last,
    }


def _no_speech_heard(words: list[WordResult]) -> bool:
    """True if nothing recognisable was heard at all.

    detect_miscues gives every expected word OMISSION with heard=None only
    when the (normalized) transcript had zero tokens — any recognised word,
    even a wrong one, turns at least one expected word into a SUBSTITUTION
    (or produces an extra). So this is an exact test for an empty transcript,
    not a heuristic over a partial/garbled one.
    """
    return bool(words) and all(
        w.status is WordStatus.OMISSION and w.heard is None for w in words
    )


def _add_routes(app: FastAPI) -> None:
    api_prefix = "/api"

    @app.get(f"{api_prefix}/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"{api_prefix}/languages")
    async def get_languages() -> list[dict[str, str]]:
        return languages_mod.list_languages()

    @app.get(f"{api_prefix}/interests")
    async def get_interests() -> list[dict[str, str]]:
        return interests_mod.list_interests()

    @app.get(f"{api_prefix}/passages")
    async def get_passages(band: str | None = None) -> list[dict[str, Any]]:
        try:
            found = passages_mod.list_passages(band)
        except ValueError:
            raise HTTPException(400, f"unknown band: {band!r}")
        return [asdict(p) for p in found]

    @app.get(f"{api_prefix}/passages/{{passage_id}}")
    async def get_passage_detail(passage_id: str) -> dict[str, Any]:
        p = passages_mod.get_passage(passage_id)
        if p is None:
            raise HTTPException(404, f"unknown passage_id: {passage_id!r}")
        return asdict(p)

    @app.post(f"{api_prefix}/passages/generate", status_code=201)
    async def generate_passage(body: dict[str, Any]) -> dict[str, Any]:
        band = body.get("band")
        if band not in passages_mod.BANDS:
            raise HTTPException(
                400, f"band must be one of {sorted(passages_mod.BANDS)}"
            )
        interests = _parse_interests(body.get("interests", []))
        student_id = body.get("student_id")
        if student_id is not None:
            if isinstance(student_id, bool) or not isinstance(student_id, int):
                raise HTTPException(400, f"bad student_id: {student_id!r}")
            if db.get_student(student_id) is None:
                raise HTTPException(400, f"unknown student_id: {student_id}")
        exclude_ids = body.get("exclude_ids", [])
        if exclude_ids is None:
            exclude_ids = []
        if not isinstance(exclude_ids, list) or not all(isinstance(i, str) for i in exclude_ids):
            raise HTTPException(400, "exclude_ids must be a list of passage ids")
        # Runs in a worker thread, outside the analysis gate: a slow model call
        # must neither block the event loop nor hold up (or wait behind) analysis.
        topic = body.get("topic")
        if topic is not None and not isinstance(topic, str):
            raise HTTPException(400, "topic must be text")
        return await asyncio.to_thread(
            generate_mod.generate_passage, band, interests, student_id, exclude_ids, topic
        )

    @app.post(f"{api_prefix}/feedback")
    async def post_feedback(body: dict[str, Any]) -> dict[str, Any]:
        words = body.get("words")
        score = body.get("score")
        if not isinstance(words, list) or not isinstance(score, dict):
            raise HTTPException(400, "words (list) and score (object) are required")
        accent_adjusted = body.get("accent_adjusted")
        if accent_adjusted is not None and not isinstance(accent_adjusted, dict):
            raise HTTPException(400, "accent_adjusted must be an object or null")
        # Worker thread, outside the analysis gate: a slow model call must not queue behind analysis.
        return await asyncio.to_thread(
            feedback_mod.make_feedback,
            words,
            score,
            accent_adjusted,
            body.get("home_language"),
        )

    @app.post(f"{api_prefix}/students", status_code=201)
    async def create_student(body: dict[str, Any]) -> dict[str, Any]:
        name = body.get("name")
        grade_band = body.get("grade_band")
        home_language = body.get("home_language")
        if not isinstance(name, str) or not name.strip():
            raise HTTPException(400, "name is required")
        if grade_band not in passages_mod.BANDS:
            raise HTTPException(
                400, f"grade_band must be one of {sorted(passages_mod.BANDS)}"
            )
        if home_language is not None and home_language not in languages_mod.known_codes():
            raise HTTPException(400, f"unknown home_language: {home_language!r}")
        interests = _parse_interests(body.get("interests", []))
        return db.create_student(
            name=name, grade_band=grade_band, home_language=home_language, interests=interests
        )

    @app.patch(f"{api_prefix}/students/{{student_id}}")
    async def update_student(student_id: int, body: dict[str, Any]) -> dict[str, Any]:
        if db.get_student(student_id) is None:
            raise HTTPException(400, f"unknown student_id: {student_id}")
        fields: dict[str, Any] = {}
        if "name" in body:
            name = body["name"]
            if not isinstance(name, str) or not name.strip():
                raise HTTPException(400, "name must be a non-empty string")
            fields["name"] = name
        if "grade_band" in body:
            if body["grade_band"] not in passages_mod.BANDS:
                raise HTTPException(
                    400, f"grade_band must be one of {sorted(passages_mod.BANDS)}"
                )
            fields["grade_band"] = body["grade_band"]
        if "home_language" in body:
            hl = body["home_language"]
            if hl is not None and hl not in languages_mod.known_codes():
                raise HTTPException(400, f"unknown home_language: {hl!r}")
            fields["home_language"] = hl
        if "interests" in body:
            fields["interests"] = _parse_interests(body["interests"])
        return db.update_student(student_id, fields)

    @app.get(f"{api_prefix}/students/{{student_id}}/passages")
    async def get_student_passages(student_id: int) -> list[dict[str, Any]]:
        if db.get_student(student_id) is None:
            raise HTTPException(400, f"unknown student_id: {student_id}")
        return _student_passages(student_id)

    @app.get(f"{api_prefix}/students")
    async def list_students() -> list[dict[str, Any]]:
        return db.list_students()

    @app.get(f"{api_prefix}/students/{{student_id}}")
    async def get_student_detail(student_id: int) -> dict[str, Any]:
        student = db.get_student(student_id)
        if student is None:
            raise HTTPException(400, f"unknown student_id: {student_id}")
        return {
            "student": student,
            "sessions": db.list_sessions(student_id),
            "most_missed": db.most_missed(student_id),
        }

    @app.post(f"{api_prefix}/analyze")
    async def analyze_endpoint(
        audio: UploadFile | None = File(None),
        passage_id: str | None = Form(None),
        student_id: str | None = Form(None),
        home_language: str | None = Form(None),
    ) -> dict[str, Any]:
        return await _analyze(audio, passage_id, student_id, home_language)


async def _analyze(
    audio: UploadFile | None,
    passage_id: str | None,
    student_id: str | None,
    home_language: str | None,
) -> dict[str, Any]:
    if audio is None:
        raise HTTPException(400, "audio is required")
    if not passage_id:
        raise HTTPException(400, "passage_id is required")

    passage = passages_mod.get_passage(passage_id)
    if passage is None:
        raise HTTPException(400, f"unknown passage_id: {passage_id!r}")

    student: dict[str, Any] | None = None
    student_id_int: int | None = None
    if student_id:
        try:
            student_id_int = int(student_id)
        except ValueError:
            raise HTTPException(400, f"bad student_id: {student_id!r}")
        student = db.get_student(student_id_int)
        if student is None:
            raise HTTPException(400, f"unknown student_id: {student_id!r}")

    resolved_language = home_language or (student["home_language"] if student else None)
    if resolved_language is not None and resolved_language not in languages_mod.known_codes():
        raise HTTPException(400, f"unknown home_language: {resolved_language!r}")
    engine_language = languages_mod.engine_language(resolved_language)

    tmp_dir = tempfile.mkdtemp(prefix="chorus_upload_")
    raw_path = os.path.join(tmp_dir, "upload.bin")
    wav_path = os.path.join(tmp_dir, "decoded.wav")
    debug: dict[str, Any] = {
        "passage_id": passage.id,
        "passage_text": passage.text,
        "content_type": audio.content_type,
        "options": None,
        "model": _model_size(),
    }
    try:
        total = 0
        with open(raw_path, "wb") as f:
            while True:
                chunk = await audio.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "recording is larger than 10 MB")
                f.write(chunk)
        debug["upload_bytes"] = total

        try:
            debug["duration_s"] = decode_to_wav(raw_path, wav_path, max_duration_s=MAX_DURATION_S)
        except AudioTooLong:
            raise HTTPException(413, "recording is longer than 120 seconds")
        except UndecodableAudio:
            raise HTTPException(422, "could not decode the uploaded audio")

        levels = wav_levels(wav_path)
        debug["levels"] = levels
        if levels["peak_dbfs"] < SILENT_PEAK_DBFS:
            debug["rejected"] = "too quiet"
            raise HTTPException(422, TOO_QUIET_MESSAGE)
        debug["normalize_gain_db"] = round(normalize_wav_peak(wav_path), 1)

        options = _analysis_options()
        debug["options"] = options
        try:
            result = await _gate.run(
                pipeline.analyze,
                wav_path,
                passage.text,
                engine_language,
                _model_size(),
                **options,
            )
        except AnalysisBusy:
            raise HTTPException(503, "the analyzer is busy right now; try again shortly")

        debug["transcript"] = result.transcript
        debug["dropped_segments"] = result.dropped_segments
        debug["words"] = [_word_to_dict(w) for w in result.words]
        debug["heard_fraction"] = round(_heard_fraction(result.words), 3)

        if _no_speech_heard(result.words) or debug["heard_fraction"] < MIN_HEARD_FRACTION:
            debug["rejected"] = "not enough reading heard"
            raise HTTPException(422, NO_SPEECH_MESSAGE)

        words_list = [_word_to_dict(w) for w in result.words]
        score_dict = asdict(result.score)
        accent_adjusted_dict = (
            asdict(result.accent_adjusted) if result.accent_adjusted is not None else None
        )
        practice_words_list = display_mod.practice_words(result.words)
        accent_ok_count = display_mod.accent_ok_count(result.words)

        session_id: int | None = None
        if student_id_int is not None:
            session = db.create_session(
                student_id=student_id_int,
                passage_id=passage.id,
                passage_title=passage.title,
                home_language=resolved_language,
                score=score_dict,
                accent_adjusted=accent_adjusted_dict,
                words=words_list,
                practice_words=practice_words_list,
                accent_ok_count=accent_ok_count,
            )
            session_id = session["id"]

        return {
            "session_id": session_id,
            "passage_id": passage.id,
            "home_language": resolved_language,
            "accent_filter_applied": accent_adjusted_dict is not None,
            "words": words_list,
            "score": score_dict,
            "accent_adjusted": accent_adjusted_dict,
            "practice_words": practice_words_list,
            "transcript": result.transcript,
        }
    finally:
        _save_debug(raw_path, wav_path, debug)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _add_static(app: FastAPI) -> None:
    """Serve web/dist at "/" with SPA fallback, if it has been built.

    Registered after every /api route above, so /api/* always matches its
    own route first; an unmatched /api/* path still falls through to here,
    so it is explicitly rejected rather than served the SPA shell.
    """
    index_html = WEB_DIST / "index.html"
    if not index_html.is_file():
        return

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404, "not found")
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_html)


app = create_app()
