"""Regression tests for the batched fee-collection math used by term-summary
and the dashboard: per-student capping and prior-term rollover credit."""
from datetime import datetime

import models


def _setup_fee_world(db_session, sample_student):
    year = datetime.now().year
    db_session.add_all([
        models.FeeStructure(grade_level="Grade 1", term="Term 1",
                            fee_type="Tuition", amount=1000, academic_year=year),
        models.FeeStructure(grade_level="Grade 1", term="Term 2",
                            fee_type="Tuition", amount=1000, academic_year=year),
        # Overpayment in Term 1: 500 should roll over into Term 2
        models.FeePayment(student_id=sample_student.id, amount=1500,
                          payment_type="Tuition", term="Term 1",
                          recorded_by="Test"),
    ])
    db_session.commit()


def test_term_summary_caps_overpayment(as_admin, db_session, sample_student):
    _setup_fee_world(db_session, sample_student)

    r = as_admin.get("/api/fees/term-summary", params={"term": "Term 1"})
    assert r.status_code == 200
    body = r.json()
    assert body["total_expected"] == 1000
    # 1500 paid but capped at the expected fee — overpayment must not inflate %
    assert body["total_collected"] == 1000
    assert body["percentage"] == 100.0


def test_term_summary_applies_rollover_credit(as_admin, db_session, sample_student):
    _setup_fee_world(db_session, sample_student)

    r = as_admin.get("/api/fees/term-summary", params={"term": "Term 2"})
    body = r.json()
    assert body["total_expected"] == 1000
    # No direct Term 2 payments, but the 500 Term 1 overpayment rolls over
    assert body["total_collected"] == 500


def test_dashboard_stats_match_rollover_logic(as_admin, db_session, sample_student):
    _setup_fee_world(db_session, sample_student)

    r = as_admin.get("/api/dashboard/stats", params={"term": "Term 2"})
    assert r.status_code == 200
    body = r.json()
    assert body["total_students"] == 1
    assert body["term_expected"] == 1000
    assert body["term_collected"] == 500
    assert body["term_pct"] == 50
    # 500 rollover < 1000 expected → still a defaulter for Term 2
    assert body["defaulters_count"] == 1

    # Fully paid for Term 1 → not a defaulter there
    r = as_admin.get("/api/dashboard/stats", params={"term": "Term 1"})
    assert r.json()["defaulters_count"] == 0
