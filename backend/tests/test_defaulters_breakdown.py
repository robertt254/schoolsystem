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

    # outstanding_balance is now the combined grand total (tuition across every
    # owing term + any activity/transport arrears) — what a parent actually
    # owes overall, not just the queried term. total_arrears mirrors it.
    assert d["outstanding_balance"] == 1500
    assert d["tuition_arrears"] == 1500
    assert d["activity_arrears"] == 0

    # The breakdown covers every owing term, oldest first
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


def test_activity_only_arrears_surfaces_as_defaulter(as_admin, db_session, sample_student):
    """A student with tuition fully settled but Transport/activity arrears
    outstanding must still appear on the Defaulters list — arrears are
    computed against fees, transport AND every activity the student is
    enrolled in, not tuition alone."""
    year = datetime.now().year
    db_session.add(models.FeeStructure(grade_level="Grade 1", term="Term 1",
                                        fee_type="Tuition", amount=1000, academic_year=year))
    db_session.add(models.FeeStructure(grade_level="General", term="Transport",
                                        fee_type="Transport - Zone A", amount=1500, academic_year=year))
    db_session.add(models.FeePayment(student_id=sample_student.id, amount=1000,
                                      payment_type="Tuition", term="Term 1", recorded_by="Test"))
    db_session.commit()

    as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Transport - Zone A",
        "academic_year": year, "enrolled_term": "Term 1"})
    # Zone A left entirely unpaid — 1500 owed, tuition is 0 owed.

    r = as_admin.get("/api/fees/defaulters", params={"term": "Term 1", "academic_year": str(year)})
    assert r.status_code == 200
    d = next((row for row in r.json() if row["student_id"] == sample_student.id), None)
    assert d is not None, "student owing only on Transport should still be a defaulter"

    assert d["tuition_arrears"] == 0
    assert d["activity_arrears"] == 1500
    assert d["outstanding_balance"] == 1500
    assert d["total_arrears"] == 1500
    assert d["activity_breakdown"] == [{
        "activity_name": "Transport - Zone A", "category": "Transport",
        "expected": 1500, "paid": 0.0, "outstanding": 1500,
    }]


def test_defaulters_combines_tuition_and_activity_arrears(as_admin, db_session, sample_student):
    """Both categories owing at once → each shown separately, total combined."""
    year = datetime.now().year
    db_session.add(models.FeeStructure(grade_level="Grade 1", term="Term 1",
                                        fee_type="Tuition", amount=1000, academic_year=year))
    db_session.add(models.FeeStructure(grade_level="General", term="Optional",
                                        fee_type="French", amount=2000, academic_year=year))
    db_session.commit()

    as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "French",
        "academic_year": year, "enrolled_term": "Term 1"})
    as_admin.post("/api/activities/payments", json={
        "student_id": sample_student.id, "activity_name": "French",
        "amount": 500, "term": "Term 1", "academic_year": year})
    # Tuition left fully unpaid (1000 owed); French partially paid (1500 owed).

    r = as_admin.get("/api/fees/defaulters", params={"term": "Term 1", "academic_year": str(year)})
    d = next(row for row in r.json() if row["student_id"] == sample_student.id)

    assert d["tuition_arrears"] == 1000
    assert d["activity_arrears"] == 1500
    assert d["outstanding_balance"] == 2500
    assert d["total_arrears"] == 2500
    assert [a["activity_name"] for a in d["activity_breakdown"]] == ["French"]
