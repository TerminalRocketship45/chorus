"""The Chorus FastAPI service: wraps chorus.pipeline.analyze() per docs/api.md.

`create_app()` is the factory; `app` (module level) is the instance uvicorn
serves (`uvicorn chorus_api.app:app`).
"""
from __future__ import annotations

import asyncio
import os
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
from . import languages as languages_mod
from . import passages as passages_mod
from .audio import AudioTooLong, UndecodableAudio, decode_to_wav
from .concurrency import AnalysisBusy, AnalysisGate

#: repo_root/web/dist — the built React app, if it exists (another agent owns web/).
WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_DURATION_S = 120.0
NO_SPEECH_MESSAGE = (
    "We couldn't hear any reading — check the microphone and try again."
)

#: Serialises chorus.pipeline.analyze calls to one at a time, 3-deep wait queue.
_gate = AnalysisGate(max_queue=3)


def _model_size() -> str:
    return os.environ.get("CHORUS_ASR_MODEL", "base.en")


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
        return db.create_student(name=name, grade_band=grade_band, home_language=home_language)

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
    try:
        raw_path = os.path.join(tmp_dir, "upload.bin")
        wav_path = os.path.join(tmp_dir, "decoded.wav")

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

        try:
            decode_to_wav(raw_path, wav_path, max_duration_s=MAX_DURATION_S)
        except AudioTooLong:
            raise HTTPException(413, "recording is longer than 120 seconds")
        except UndecodableAudio:
            raise HTTPException(422, "could not decode the uploaded audio")

        try:
            result = await _gate.run(
                pipeline.analyze, wav_path, passage.text, engine_language, _model_size()
            )
        except AnalysisBusy:
            raise HTTPException(503, "the analyzer is busy right now; try again shortly")

        if _no_speech_heard(result.words):
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
        }
    finally:
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
