"""RBAC: the secretary handles fee operations (payments, invoices, statements)
but has no access to payroll, expenses, budgets or petty cash."""
import pytest

import models
from main import app
from auth import get_password_hash
import auth as auth_module


@pytest.fixture
def secretary_user(db_session):
    user = models.User(
        username="front_office", hashed_password=get_password_hash("irrelevant-pw"),
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


def test_secretary_can_record_payment(as_secretary, sample_student):
    r = as_secretary.post("/api/fees/", json={
        "student_id": sample_student.id, "amount": 2000,
        "payment_type": "Tuition", "term": "Term 1", "current_term": "Term 1"})
    assert r.status_code == 200
    assert r.json()["receipt_number"].startswith("BNS-")


def test_secretary_can_generate_invoice_and_view_statement(as_secretary, sample_student):
    # "Generate invoice" = carry-forward charge
    r = as_secretary.post("/api/fees/carry-forward", json={
        "student_id": sample_student.id, "amount": 5000,
        "academic_year": "2026", "term": "Term 1", "note": "Manual invoice"})
    assert r.status_code == 201

    # Statement building blocks: payments, balance, carry-forwards, log
    assert as_secretary.get(f"/api/fees/student/{sample_student.id}").status_code == 200
    assert as_secretary.get(f"/api/fees/balance/{sample_student.id}/Term 1").status_code == 200
    assert as_secretary.get(f"/api/fees/carry-forward/{sample_student.id}").status_code == 200
    assert as_secretary.get("/api/fees/log").status_code == 200
    assert as_secretary.get("/api/fees/defaulters", params={"term": "Term 1"}).status_code == 200


def test_secretary_can_record_bulk_payments(as_secretary, sample_student):
    r = as_secretary.post("/api/fees/bulk", json=[{
        "student_id": sample_student.id, "amount": 1000,
        "payment_type": "Tuition", "term": "Term 1"}])
    assert r.status_code == 201
    assert r.json()["created"] == 1


def test_secretary_blocked_from_school_finances(as_secretary):
    assert as_secretary.get("/api/finance/payroll/monthly", params={"month": "2026-07"}).status_code == 403
    assert as_secretary.get("/api/finance/expenses").status_code == 403
    assert as_secretary.get("/api/finance/budget").status_code == 403
    assert as_secretary.get("/api/finance/petty-cash").status_code == 403
    assert as_secretary.get("/api/finance/term-accountability").status_code == 403
