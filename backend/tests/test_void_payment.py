"""Voiding corrects a mistaken fee entry without erasing it: admin/principal
only, a reason is required, the row stays (for accountability — shown in
the payment log with who voided it, when, and why), and every arrears/
collection figure excludes it immediately."""
from datetime import datetime
import pytest
import models
from main import app
from auth import get_password_hash
import auth as auth_module


@pytest.fixture
def secretary_user(db_session):
    user = models.User(
        username="front_office3", hashed_password=get_password_hash("irrelevant-pw"),
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


def _record_tuition_payment(client, student_id, amount, term="Term 1"):
    r = client.post("/api/fees/", json={
        "student_id": student_id, "amount": amount,
        "payment_type": "Tuition", "term": term, "current_term": term,
    })
    assert r.status_code == 200
    return r.json()["id"]


def test_void_requires_a_reason(as_admin, sample_student):
    payment_id = _record_tuition_payment(as_admin, sample_student.id, 1000)
    r = as_admin.post(f"/api/fees/{payment_id}/void", json={"reason": ""})
    assert r.status_code == 422  # min_length=3


def test_secretary_cannot_void(as_secretary, db_session, sample_student):
    # Built directly in the DB, not via as_admin — that fixture would
    # overwrite as_secretary's auth override (both mutate the same
    # app.dependency_overrides entry), making the later call run as admin.
    payment = models.FeePayment(
        student_id=sample_student.id, amount=1000, payment_type="Tuition",
        term="Term 1", recorded_by="Test", receipt_number="BNS-TEST-1")
    db_session.add(payment)
    db_session.commit()

    r = as_secretary.post(f"/api/fees/{payment.id}/void", json={"reason": "wrong amount"})
    assert r.status_code == 403


def test_admin_can_void_with_reason(as_admin, sample_student):
    payment_id = _record_tuition_payment(as_admin, sample_student.id, 1000)
    r = as_admin.post(f"/api/fees/{payment_id}/void", json={"reason": "entered wrong amount"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_voided"] is True
    assert body["void_reason"] == "entered wrong amount"
    assert body["voided_by"] == "Sys Admin"
    assert body["voided_at"] is not None


def test_cannot_void_twice(as_admin, sample_student):
    payment_id = _record_tuition_payment(as_admin, sample_student.id, 1000)
    as_admin.post(f"/api/fees/{payment_id}/void", json={"reason": "mistake"})
    r = as_admin.post(f"/api/fees/{payment_id}/void", json={"reason": "again"})
    assert r.status_code == 400


def test_voiding_restores_tuition_balance(as_admin, db_session, sample_student):
    year = datetime.now().year
    db_session.add(models.FeeStructure(grade_level="Grade 1", term="Term 1",
                                        fee_type="Tuition", amount=1000, academic_year=year))
    db_session.commit()
    payment_id = _record_tuition_payment(as_admin, sample_student.id, 1000)

    r = as_admin.get(f"/api/fees/balance/{sample_student.id}/Term 1")
    assert r.json()["outstanding_balance"] == 0

    as_admin.post(f"/api/fees/{payment_id}/void", json={"reason": "wrong student"})

    r = as_admin.get(f"/api/fees/balance/{sample_student.id}/Term 1")
    assert r.json()["outstanding_balance"] == 1000

    # Defaulters list now includes them again
    r = as_admin.get("/api/fees/defaulters", params={"term": "Term 1"})
    ids = [d["student_id"] for d in r.json()]
    assert sample_student.id in ids


def test_voided_payment_excluded_from_collection_reports(as_admin, sample_student):
    payment_id = _record_tuition_payment(as_admin, sample_student.id, 1000)
    as_admin.post(f"/api/fees/{payment_id}/void", json={"reason": "duplicate entry"})

    r = as_admin.get("/api/fees/collection-summary")
    for row in r.json():
        assert row["total_paid"] == 0

    year = datetime.now().year
    r = as_admin.get("/api/fees/monthly-collection", params={"year": year})
    assert sum(m["total"] for m in r.json()) == 0

    r = as_admin.get("/api/dashboard/stats", params={"term": "Term 1"})
    assert r.json()["total_revenue"] == 0


def test_voiding_an_activity_payment_restores_its_balance(as_admin, db_session, sample_student):
    year = datetime.now().year
    db_session.add(models.FeeStructure(grade_level="General", term="Optional",
                                        fee_type="Swimming", amount=2000, academic_year=year))
    db_session.commit()
    as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Swimming",
        "academic_year": year, "enrolled_term": "Term 1"})
    r = as_admin.post("/api/activities/payments", json={
        "student_id": sample_student.id, "activity_name": "Swimming",
        "amount": 2000, "term": "Term 1", "academic_year": year})
    payment_id = r.json()["id"]

    roster = as_admin.get("/api/activities/Swimming/roster",
                           params={"term": "Term 1", "academic_year": year}).json()
    assert roster["entries"][0]["outstanding"] == 0

    as_admin.post(f"/api/fees/{payment_id}/void", json={"reason": "paid under wrong activity"})

    roster = as_admin.get("/api/activities/Swimming/roster",
                           params={"term": "Term 1", "academic_year": year}).json()
    assert roster["entries"][0]["outstanding"] == 2000
    assert roster["entries"][0]["paid"] == 0


def test_payment_log_shows_void_details(as_admin, sample_student):
    payment_id = _record_tuition_payment(as_admin, sample_student.id, 1000)
    as_admin.post(f"/api/fees/{payment_id}/void", json={"reason": "keyed in twice"})

    r = as_admin.get("/api/fees/log")
    row = next(x for x in r.json() if x["id"] == payment_id)
    assert row["status"] == "voided"
    assert row["void_reason"] == "keyed in twice"
    assert row["voided_by"] == "Sys Admin"
    assert row["voided_at"] is not None
    # The row's own payment_date/receipt/amount are still there — nothing erased
    assert row["amount"] == 1000
    assert row["receipt_number"].startswith("BNS-")
