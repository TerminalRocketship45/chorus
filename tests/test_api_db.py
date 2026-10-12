"""Direct tests of chorus_api.db: schema, session ordering, most_missed, and
the "never store audio" contract (no column could even hold it)."""
import pytest

from chorus_api import db


@pytest.fixture
def path(tmp_path):
    p = str(tmp_path / "chorus.db")
    db.init_db(p)
    return p


def test_init_db_is_idempotent(path):
    db.init_db(path)  # second call must not raise
    db.init_db(path)


def test_create_and_get_student(path):
    created = db.create_student("Amina", "elementary", "somali", path)
    fetched = db.get_student(created["id"], path)
    assert fetched == created


def test_get_unknown_student_returns_none(path):
    assert db.get_student(999, path) is None


def test_sessions_are_returned_oldest_first(path):
    student = db.create_student("Amina", "elementary", None, path)
    score = {
        "accuracy": 1.0,
        "wcpm": 80.0,
        "total_words": 5,
        "correct_words": 5,
        "duration_s": 3.0,
        "long_pauses": 0,
    }
    ids = []
    for i in range(3):
        s = db.create_session(
            student_id=student["id"],
            passage_id=f"el-0{i + 1}",
            passage_title=f"Passage {i + 1}",
            home_language=None,
            score=score,
            accent_adjusted=None,
            words=[],
            practice_words=[],
            accent_ok_count=0,
            path=path,
        )
        ids.append(s["id"])

    sessions = db.list_sessions(student["id"], path)
    assert [s["id"] for s in sessions] == ids
    assert [s["passage_id"] for s in sessions] == ["el-01", "el-02", "el-03"]


def test_create_session_never_has_an_audio_field(path):
    """Schema-level guard for the "recordings are never stored" rule."""
    import sqlite3

    conn = sqlite3.connect(path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
    conn.close()
    assert not any("audio" in c.lower() for c in cols)


def _word(expected, display):
    return {"index": 0, "expected": expected, "heard": None, "status": "x", "display": display}


def test_most_missed_counts_misread_and_skipped_across_sessions(path):
    student = db.create_student("Amina", "elementary", None, path)
    score = {
        "accuracy": 0.5,
        "wcpm": 50.0,
        "total_words": 2,
        "correct_words": 1,
        "duration_s": 2.0,
        "long_pauses": 0,
    }
    db.create_session(
        student_id=student["id"],
        passage_id="el-01",
        passage_title="P1",
        home_language=None,
        score=score,
        accent_adjusted=None,
        words=[
            _word("through", "misread"),
            _word("cat", "skipped"),
            _word("the", "correct"),
        ],
        practice_words=["through", "cat"],
        accent_ok_count=0,
        path=path,
    )
    db.create_session(
        student_id=student["id"],
        passage_id="el-02",
        passage_title="P2",
        home_language=None,
        score=score,
        accent_adjusted=None,
        words=[
            _word("through", "misread"),
            _word("mat", "misread"),
        ],
        practice_words=["through", "mat"],
        accent_ok_count=0,
        path=path,
    )

    result = db.most_missed(student["id"], path)
    assert result[0] == {"word": "through", "count": 2}
    assert {"word": "cat", "count": 1} in result
    assert {"word": "mat", "count": 1} in result
    assert all(r["word"] != "the" for r in result)  # "correct" is not a miss


def test_most_missed_caps_at_ten(path):
    student = db.create_student("Amina", "elementary", None, path)
    score = {
        "accuracy": 0.0,
        "wcpm": 0.0,
        "total_words": 12,
        "correct_words": 0,
        "duration_s": 2.0,
        "long_pauses": 0,
    }
    words = [_word(f"word{i}", "misread") for i in range(12)]
    db.create_session(
        student_id=student["id"],
        passage_id="el-01",
        passage_title="P1",
        home_language=None,
        score=score,
        accent_adjusted=None,
        words=words,
        practice_words=[w["expected"] for w in words],
        accent_ok_count=0,
        path=path,
    )
    assert len(db.most_missed(student["id"], path)) == 10


def test_list_students_last_wcpm_reflects_most_recent_session(path):
    student = db.create_student("Amina", "elementary", None, path)
    for wcpm in (40.0, 55.0):
        db.create_session(
            student_id=student["id"],
            passage_id="el-01",
            passage_title="P1",
            home_language=None,
            score={
                "accuracy": 1.0,
                "wcpm": wcpm,
                "total_words": 5,
                "correct_words": 5,
                "duration_s": 3.0,
                "long_pauses": 0,
            },
            accent_adjusted=None,
            words=[],
            practice_words=[],
            accent_ok_count=0,
            path=path,
        )
    students = db.list_students(path)
    assert students[0]["session_count"] == 2
    assert students[0]["last_wcpm"] == 55.0
