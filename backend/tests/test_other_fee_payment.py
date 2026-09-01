"""POST /api/fees/other records fee-receipt line items with no arrears
concept (Admission, Diary, Lunch, Computer, Tour, Medical, Graduation,
Miscellaneous) — flat, not run through the tuition waterfall."""
import models


def test_record_other_payment_is_flat_not_waterfalled(as_admin, sample_student):
    r = as_admin.post("/api/fees/other", json={
        "student_id": sample_student.id, "fee_item": "Diary",
        "amount": 500, "term": "Term 1",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["payment_type"] == "Other"
    assert body["activity"] == "Diary"
    assert body["term"] == "Term 1"
    assert body["receipt_number"].startswith("BNS-")
    # No waterfall means no allocation breakdown
    assert not body["allocation"]


def test_other_payment_does_not_touch_tuition_balance(as_admin, db_session, sample_student):
    from datetime import datetime
    year = datetime.now().year
    db_session.add(models.FeeStructure(grade_level="Grade 1", term="Term 1",
                                        fee_type="Tuition", amount=1000, academic_year=year))
    db_session.commit()

    as_admin.post("/api/fees/other", json={
        "student_id": sample_student.id, "fee_item": "Admission",
        "amount": 1500, "term": "Term 1",
    })

    r = as_admin.get(f"/api/fees/balance/{sample_student.id}/Term 1")
    # Tuition is still fully outstanding — the Admission payment didn't
    # clear it, unlike a Tuition-tagged payment through record_payment would.
    assert r.json()["outstanding_balance"] == 1000


def test_other_payment_rejects_unknown_student(as_admin):
    r = as_admin.post("/api/fees/other", json={
        "student_id": 999999, "fee_item": "Lunch", "amount": 200, "term": "Term 1",
    })
    assert r.status_code == 404
