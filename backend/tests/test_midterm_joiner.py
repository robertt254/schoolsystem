"""A student who joins mid-year owes fees only from their admission term:
no phantom Term 1 arrears, no wrong waterfall allocation, no false
defaulter listing, and dashboard expectations that match reality."""
from datetime import datetime

import pytest

import models


YEAR = datetime.now().year


@pytest.fixture
def fee_world(db_session):
    db_session.add_all([
        models.FeeStructure(grade_level="Grade 1", term="Term 1",
                            fee_type="Tuition", amount=1000, academic_year=YEAR),
        models.FeeStructure(grade_level="Grade 1", term="Term 2",
                            fee_type="Tuition", amount=1000, academic_year=YEAR),
        models.FeeStructure(grade_level="Grade 1", term="Term 3",
                            fee_type="Tuition", amount=1000, academic_year=YEAR),
    ])
    db_session.commit()


@pytest.fixture
def term2_joiner(db_session):
    s = models.Student(
        first_name="New", last_name="Joiner", admission_number="BNS-0900",
        grade_level="Grade 1", status="Active",
        admission_term="Term 2", admission_year=YEAR,
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


def test_no_balance_for_terms_before_admission(as_admin, fee_world, term2_joiner):
    r = as_admin.get(f"/api/fees/balance/{term2_joiner.id}/Term 1")
    assert r.json()["expected_term_fee"] == 0
    assert r.json()["outstanding_balance"] == 0

    r = as_admin.get(f"/api/fees/balance/{term2_joiner.id}/Term 2")
    assert r.json()["expected_term_fee"] == 1000
    assert r.json()["outstanding_balance"] == 1000


def test_bulk_payment_skips_preadmission_terms(as_admin, fee_world, term2_joiner):
    # 1000 paid in Term 2 must go to Term 2 — NOT to phantom Term 1 arrears
    r = as_admin.post("/api/fees/bulk", json=[{
        "student_id": term2_joiner.id, "amount": 1000,
        "payment_type": "Tuition", "term": "Term 2"}])
    assert r.status_code == 201

    payment = as_admin.get(f"/api/fees/student/{term2_joiner.id}").json()[0]
    assert payment["term"] == "Term 2"
    assert payment["allocation"] == [{"term": "Term 2", "amount": 1000, "kind": "current"}]

    assert as_admin.get(f"/api/fees/balance/{term2_joiner.id}/Term 2").json()["outstanding_balance"] == 0


def test_not_a_defaulter_for_preadmission_terms(as_admin, fee_world, term2_joiner):
    defaulters = as_admin.get("/api/fees/defaulters", params={"term": "Term 1"}).json()
    assert all(d["student_id"] != term2_joiner.id for d in defaulters)

    # But unpaid for Term 2 (their admission term) they ARE a defaulter
    defaulters = as_admin.get("/api/fees/defaulters", params={"term": "Term 2"}).json()
    assert any(d["student_id"] == term2_joiner.id for d in defaulters)


def test_dashboard_expectations_exclude_preadmission(as_admin, fee_world, term2_joiner):
    r = as_admin.get("/api/dashboard/stats", params={"term": "Term 1"})
    assert r.json()["term_expected"] == 0          # only student joined in Term 2
    assert r.json()["defaulters_count"] == 0

    r = as_admin.get("/api/dashboard/stats", params={"term": "Term 2"})
    assert r.json()["term_expected"] == 1000
    assert r.json()["defaulters_count"] == 1


def test_legacy_students_still_owe_all_terms(as_admin, fee_world, sample_student):
    # sample_student has no admission fields — the pre-existing behaviour holds
    r = as_admin.get(f"/api/fees/balance/{sample_student.id}/Term 1")
    assert r.json()["expected_term_fee"] == 1000
    assert r.json()["outstanding_balance"] == 1000