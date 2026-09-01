"""Transport is split into two independently priced, independently
subscribed zones — Zone A (closer to school) and Zone B (further away).
No dedicated zone logic was needed in the activity engine: each zone is
just its own activity_name under the Transport category, which the existing
subscription/roster/payment machinery already handles generically."""
from datetime import datetime
import models


def _add_zone_fee(db_session, zone_name, amount, year=None):
    year = year or datetime.now().year
    db_session.add(models.FeeStructure(
        grade_level="General", term="Transport", fee_type=zone_name,
        amount=amount, academic_year=year))
    db_session.commit()


def test_two_zones_are_independent_activities(as_admin, db_session, sample_student):
    year = datetime.now().year
    _add_zone_fee(db_session, "Transport - Zone A", 1500, year)
    _add_zone_fee(db_session, "Transport - Zone B", 2500, year)

    r = as_admin.get("/api/activities/", params={"year": year, "category": "Transport"})
    names = sorted(a["activity_name"] for a in r.json())
    assert names == ["Transport - Zone A", "Transport - Zone B"]

    r = as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Transport - Zone B",
        "academic_year": year, "enrolled_term": "Term 1"})
    assert r.status_code == 201

    # Zone A roster is empty; Zone B has the subscriber with its own price.
    a_roster = as_admin.get("/api/activities/Transport - Zone A/roster",
                             params={"term": "Term 1", "academic_year": year}).json()
    b_roster = as_admin.get("/api/activities/Transport - Zone B/roster",
                             params={"term": "Term 1", "academic_year": year}).json()
    assert a_roster["entries"] == []
    assert b_roster["entries"][0]["student_id"] == sample_student.id
    assert b_roster["entries"][0]["expected"] == 2500


def test_student_activity_standing_reports_zone_and_arrears(as_admin, db_session, sample_student):
    year = datetime.now().year
    _add_zone_fee(db_session, "Transport - Zone A", 1500, year)
    as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Transport - Zone A",
        "academic_year": year, "enrolled_term": "Term 1"})
    as_admin.post("/api/activities/payments", json={
        "student_id": sample_student.id, "activity_name": "Transport - Zone A",
        "amount": 500, "term": "Term 1", "academic_year": year})

    r = as_admin.get(f"/api/activities/student/{sample_student.id}/standing",
                      params={"term": "Term 1", "academic_year": year})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["activity_name"] == "Transport - Zone A"
    assert rows[0]["category"] == "Transport"
    assert rows[0]["expected"] == 1500
    assert rows[0]["paid"] == 500
    assert rows[0]["outstanding"] == 1000
    assert rows[0]["compulsory"] is False


def test_activity_payment_does_not_inflate_tuition_paid(as_admin, db_session, sample_student):
    """Regression test: activity/transport payments are tagged with the same
    `term` field as tuition payments for record-keeping, but must never be
    counted toward tuition's paid sum — fees.py's tuition queries all filter
    activity IS NULL specifically to prevent this."""
    year = datetime.now().year
    db_session.add(models.FeeStructure(grade_level="Grade 1", term="Term 1",
                                        fee_type="Tuition", amount=1000, academic_year=year))
    _add_zone_fee(db_session, "Transport - Zone A", 1500, year)
    as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "Transport - Zone A",
        "academic_year": year, "enrolled_term": "Term 1"})
    as_admin.post("/api/activities/payments", json={
        "student_id": sample_student.id, "activity_name": "Transport - Zone A",
        "amount": 1500, "term": "Term 1", "academic_year": year})

    r = as_admin.get(f"/api/fees/balance/{sample_student.id}/Term 1")
    assert r.json()["total_paid_this_term"] == 0
    assert r.json()["outstanding_balance"] == 1000

    r = as_admin.get("/api/fees/defaulters", params={"term": "Term 1"})
    defaulter = next(d for d in r.json() if d["student_id"] == sample_student.id)
    assert defaulter["total_paid"] == 0
    assert defaulter["outstanding_balance"] == 1000


def test_student_activity_standing_flags_french_as_compulsory(as_admin, sample_student, db_session):
    year = datetime.now().year
    db_session.add(models.FeeStructure(grade_level="General", term="Optional",
                                        fee_type="French", amount=2000, academic_year=year))
    db_session.commit()
    as_admin.post("/api/activities/enrollments", json={
        "student_id": sample_student.id, "activity_name": "French",
        "academic_year": year, "enrolled_term": "Term 1"})

    r = as_admin.get(f"/api/activities/student/{sample_student.id}/standing",
                      params={"term": "Term 1", "academic_year": year})
    row = next(x for x in r.json() if x["activity_name"] == "French")
    assert row["compulsory"] is True
