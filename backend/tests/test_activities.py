"""Transport & co-curricular activity subscriptions and per-activity arrears.
Mirrors the tuition waterfall tests in test_fees_summary.py, but for the
separate ActivityEnrollment engine in activities.py."""
from datetime import datetime

import pytest
import models
from main import app
from auth import get_password_hash
import auth as auth_module


def _add_activity_fee(db_session, name, category, amount, year=None):
    year = year or datetime.now().year
    db_session.add(models.FeeStructure(
        grade_level="General", term=category, fee_type=name,
        amount=amount, academic_year=year))
    db_session.commit()


@pytest.fixture
def secretary_user(db_session):
    user = models.User(
        username="front_office2", hashed_password=get_password_hash("irrelevant-pw"),
        name="Front Office", role="secretary", can_login=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def as_secretary(client, secretary_user):
    app.dependency_overrides[auth_module.get_current_user] = lambda: secretary_user
    return client


@pytest.fixture
def teacher_user(db_session):
    user = models.User(
        username="mr_kamau", hashed_password=get_password_hash("irrelevant-pw"),
        name="Mr Kamau", role="teacher", can_login=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def as_teacher(client, teacher_user):
    app.dependency_overrides[auth_module.get_current_user] = lambda: teacher_user
    return client


def test_subscribe_and_roster_shows_arrears(as_admin, db_session, sample_student):
    year = datetime.now().year
    _add_activity_fee(db_session, "Transport", "Transport", 1500, year)

    r = as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Transport",
        "academic_year": year, "enrolled_term": "Term 1"})
    assert r.status_code == 201
    assert r.json()["is_active"] is True

    # No payments yet — Term 2 roster should show 2 terms owed (1 & 2)
    r = as_admin.get("/api/activities/Transport/roster", params={"term": "Term 2", "academic_year": year})
    assert r.status_code == 200
    body = r.json()
    assert body["total_expected"] == 3000
    assert body["total_paid"] == 0
    assert body["total_outstanding"] == 3000
    assert body["entries"][0]["student_id"] == sample_student.id


def test_activity_payment_reduces_arrears_and_is_tagged(as_admin, db_session, sample_student):
    year = datetime.now().year
    _add_activity_fee(db_session, "Swimming", "Optional", 2000, year)
    as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Swimming",
        "academic_year": year, "enrolled_term": "Term 1"})

    r = as_admin.post("/api/activities/payments", json={
        "student_id": sample_student.id, "activity_name": "Swimming",
        "amount": 1200, "term": "Term 1", "academic_year": year})
    assert r.status_code == 201
    body = r.json()
    assert body["activity"] == "Swimming"
    assert body["payment_type"] == "Co-curricular"
    assert body["receipt_number"].startswith("BNS-")

    r = as_admin.get("/api/activities/Swimming/roster", params={"term": "Term 1", "academic_year": year})
    entry = r.json()["entries"][0]
    assert entry["expected"] == 2000
    assert entry["paid"] == 1200
    assert entry["outstanding"] == 800


def test_mid_year_activity_join_owes_only_from_enrolled_term(as_admin, db_session, sample_student):
    year = datetime.now().year
    _add_activity_fee(db_session, "Transport", "Transport", 1000, year)
    as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Transport",
        "academic_year": year, "enrolled_term": "Term 2"})

    # Term 1 roster: joined in Term 2, so nothing owed for Term 1 yet
    r = as_admin.get("/api/activities/Transport/roster", params={"term": "Term 1", "academic_year": year})
    assert r.json()["entries"][0]["expected"] == 0

    # Term 2 roster: one term owed
    r = as_admin.get("/api/activities/Transport/roster", params={"term": "Term 2", "academic_year": year})
    assert r.json()["entries"][0]["expected"] == 1000


def test_unsubscribe_keeps_arrears_but_flags_inactive(as_admin, db_session, sample_student):
    year = datetime.now().year
    _add_activity_fee(db_session, "Ballet", "Optional", 3000, year)
    r = as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Ballet",
        "academic_year": year, "enrolled_term": "Term 1"})
    enrollment_id = r.json()["id"]

    r = as_admin.delete(f"/api/activities/enrollments/{enrollment_id}")
    assert r.status_code == 204

    r = as_admin.get("/api/activities/Ballet/roster", params={"term": "Term 1", "academic_year": year})
    entry = r.json()["entries"][0]
    assert entry["is_active"] is False
    assert entry["outstanding"] == 3000  # still collectible after dropping


def test_cannot_double_subscribe_active_enrollment(as_admin, db_session, sample_student):
    year = datetime.now().year
    _add_activity_fee(db_session, "Coding", "Optional", 0, year)
    as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Coding",
        "academic_year": year, "enrolled_term": "Term 1"})
    r = as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Coding",
        "academic_year": year, "enrolled_term": "Term 1"})
    assert r.status_code == 400


def test_secretary_can_manage_activities(as_secretary, db_session, sample_student):
    year = datetime.now().year
    _add_activity_fee(db_session, "Transport", "Transport", 1500, year)
    r = as_secretary.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Transport",
        "academic_year": year, "enrolled_term": "Term 1"})
    assert r.status_code == 201
    assert as_secretary.get("/api/activities/Transport/roster",
                             params={"term": "Term 1", "academic_year": year}).status_code == 200


def test_teacher_blocked_from_activities(as_teacher, db_session, sample_student):
    year = datetime.now().year
    _add_activity_fee(db_session, "Transport", "Transport", 1500, year)
    r = as_teacher.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Transport",
        "academic_year": year, "enrolled_term": "Term 1"})
    assert r.status_code == 403
    assert as_teacher.get("/api/activities/", params={"year": year}).status_code == 403
