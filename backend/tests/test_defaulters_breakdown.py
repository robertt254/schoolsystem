"""The Defaulters page prints per-student arrears invoices from a
term_breakdown/total_arrears the /api/fees/defaulters endpoint now returns,
covering every term still owed — not just the one queried."""
from datetime import datetime

import models


def test_defaulters_includes_full_term_breakdown(as_admin, db_session, sample_student):
    year = datetime.now().year
    db_session.add_all([
        models.FeeStructure(grade_level="Grade 1", term="Term 1",
                            fee_type="Tuition", amount=1000, academic_year=year),
        models.FeeStructure(grade_level="Grade 1", term="Term 2",
                            fee_type="Tuition", amount=1000, academic_year=year),
        # Only half of Term 1 paid; nothing paid for Term 2 yet.
        models.FeePayment(student_id=sample_student.id, amount=500,
                          payment_type="Tuition", term="Term 1", recorded_by="Test"),
    ])
    db_session.commit()

    r = as_admin.get("/api/fees/defaulters", params={"term": "Term 2"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    d = body[0]

    # The existing single-term field still reflects Term 2 only
    assert d["outstanding_balance"] == 1000

    # The new breakdown covers every owing term, oldest first
    assert d["term_breakdown"] == [
        {"term": "Term 1", "expected": 1000, "paid": 500, "carry_forward": 0.0, "outstanding": 500},
        {"term": "Term 2", "expected": 1000, "paid": 0.0, "carry_forward": 0.0, "outstanding": 1000},
    ]
    assert d["total_arrears"] == 1500


def test_defaulters_breakdown_omits_settled_terms(as_admin, db_session, sample_student):
    year = datetime.now().year
    db_session.add_all([
        models.FeeStructure(grade_level="Grade 1", term="Term 1",
                            fee_type="Tuition", amount=1000, academic_year=year),
        models.FeeStructure(grade_level="Grade 1", term="Term 2",
                            fee_type="Tuition", amount=1000, academic_year=year),
        # Term 1 fully paid; Term 2 unpaid.
        models.FeePayment(student_id=sample_student.id, amount=1000,
                          payment_type="Tuition", term="Term 1", recorded_by="Test"),
    ])
    db_session.commit()

    r = as_admin.get("/api/fees/defaulters", params={"term": "Term 2"})
    d = r.json()[0]

    # Only the still-owing term appears in the breakdown
    assert [row["term"] for row in d["term_breakdown"]] == ["Term 2"]
    assert d["total_arrears"] == 1000
