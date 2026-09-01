"""Security audit (2026-09-01): several GET/write endpoints authenticated any
logged-in user but applied no role check at all, unlike every sibling
endpoint in the same file. Each of these mirrors the role set already
enforced on the corresponding write/sibling endpoint in its own module."""
from datetime import datetime
import pytest
import models
from main import app
from auth import get_password_hash
import auth as auth_module


def _make_user(db_session, username, role):
    user = models.User(
        username=username, hashed_password=get_password_hash("irrelevant-pw"),
        name=username.replace("_", " ").title(), role=role, can_login=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def as_role(client, db_session):
    created = {}

    def _for(role):
        if role not in created:
            created[role] = _make_user(db_session, f"audit_{role}", role)
        app.dependency_overrides[auth_module.get_current_user] = lambda: created[role]
        return client
    return _for


def test_report_card_blocked_for_secretary_and_accountant(as_role, sample_student):
    for role in ["secretary", "accountant"]:
        r = as_role(role).get(f"/api/academics/report-card/{sample_student.id}/Term 1")
        assert r.status_code == 403
    r = as_role("principal").get(f"/api/academics/report-card/{sample_student.id}/Term 1")
    assert r.status_code == 200


def test_exam_merit_list_blocked_for_secretary_and_accountant(as_role):
    year = datetime.now().year
    for role in ["secretary", "accountant"]:
        r = as_role(role).get("/api/exams/grade/Grade 1/Term 1",
                               params={"academic_year": year, "exam_type": "Opener"})
        assert r.status_code == 403
    r = as_role("admin").get("/api/exams/grade/Grade 1/Term 1",
                              params={"academic_year": year, "exam_type": "Opener"})
    assert r.status_code == 200


def test_exam_student_results_blocked_for_secretary(as_role, sample_student):
    r = as_role("secretary").get(f"/api/exams/student/{sample_student.id}")
    assert r.status_code == 403
    r = as_role("senior_teacher").get(f"/api/exams/student/{sample_student.id}")
    assert r.status_code == 200


def test_exam_performance_summary_blocked_for_accountant(as_role):
    r = as_role("accountant").get("/api/exams/performance-summary")
    assert r.status_code == 403
    r = as_role("principal").get("/api/exams/performance-summary")
    assert r.status_code == 200


def test_discipline_list_blocked_for_accountant(as_role):
    r = as_role("accountant").get("/api/discipline/")
    assert r.status_code == 403
    r = as_role("secretary").get("/api/discipline/")
    assert r.status_code == 200


def test_fees_collection_summary_blocked_for_secretary(as_role):
    """Same 'what the school makes' sensitivity as dashboard net revenue —
    secretary is deliberately excluded there too (see dashboard.py)."""
    r = as_role("secretary").get("/api/fees/collection-summary")
    assert r.status_code == 403
    r = as_role("accountant").get("/api/fees/collection-summary")
    assert r.status_code == 200


def test_library_borrow_actions_blocked_for_accountant(as_role, db_session):
    book = models.LibraryBook(title="Test Book", quantity=1, available=1)
    db_session.add(book)
    db_session.commit()
    db_session.refresh(book)

    r = as_role("accountant").post("/api/library/borrows", json={
        "book_id": book.id, "borrower_type": "student", "borrower_id": 1,
        "borrower_name": "Test Student", "due_date": "2026-12-01",
    })
    assert r.status_code == 403

    r = as_role("secretary").post("/api/library/borrows", json={
        "book_id": book.id, "borrower_type": "student", "borrower_id": 1,
        "borrower_name": "Test Student", "due_date": "2026-12-01",
    })
    assert r.status_code == 201
    borrow_id = r.json()["id"]

    r = as_role("accountant").put(f"/api/library/borrows/{borrow_id}/return")
    assert r.status_code == 403
    r = as_role("secretary").put(f"/api/library/borrows/{borrow_id}/return")
    assert r.status_code == 200
