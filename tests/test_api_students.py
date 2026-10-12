import pytest
from fastapi.testclient import TestClient

from chorus_api.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHORUS_DB", str(tmp_path / "chorus.db"))
    with TestClient(app) as c:
        yield c


def test_create_student(client):
    r = client.post(
        "/api/students",
        json={"name": "Amina", "grade_band": "elementary", "home_language": "somali"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Amina"
    assert body["grade_band"] == "elementary"
    assert body["home_language"] == "somali"
    assert isinstance(body["id"], int)
    assert body["created_at"]


def test_create_student_without_home_language(client):
    r = client.post("/api/students", json={"name": "Jordan", "grade_band": "secondary"})
    assert r.status_code == 201
    assert r.json()["home_language"] is None


def test_create_student_missing_name_is_400(client):
    r = client.post("/api/students", json={"grade_band": "elementary"})
    assert r.status_code == 400


def test_create_student_blank_name_is_400(client):
    r = client.post("/api/students", json={"name": "   ", "grade_band": "elementary"})
    assert r.status_code == 400


def test_create_student_bad_grade_band_is_400(client):
    r = client.post("/api/students", json={"name": "Amina", "grade_band": "middle"})
    assert r.status_code == 400


def test_create_student_bad_home_language_is_400(client):
    r = client.post(
        "/api/students",
        json={"name": "Amina", "grade_band": "elementary", "home_language": "klingon"},
    )
    assert r.status_code == 400


def test_list_students_includes_session_stats(client):
    client.post("/api/students", json={"name": "Amina", "grade_band": "elementary"})
    r = client.get("/api/students")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["session_count"] == 0
    assert body[0]["last_session_at"] is None
    assert body[0]["last_wcpm"] is None


def test_list_students_is_empty_initially(client):
    r = client.get("/api/students")
    assert r.status_code == 200
    assert r.json() == []


def test_get_student_detail(client):
    created = client.post(
        "/api/students", json={"name": "Amina", "grade_band": "elementary"}
    ).json()
    r = client.get(f"/api/students/{created['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["student"]["id"] == created["id"]
    assert body["sessions"] == []
    assert body["most_missed"] == []


def test_get_unknown_student_is_400(client):
    r = client.get("/api/students/999")
    assert r.status_code == 400
    assert "detail" in r.json()
