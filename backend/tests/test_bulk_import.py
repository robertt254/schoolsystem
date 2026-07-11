"""Bulk student import and backdated payments — paper-records migration aids."""
from datetime import datetime

import models


def test_bulk_import_students_generates_admission_numbers(as_admin):
    r = as_admin.post("/api/students/bulk", json=[
        {"first_name": "Amina", "last_name": "Yusuf", "grade_level": "PP1",
         "gender": "Female", "guardian_phone": "+254700000010"},
        {"first_name": "Brian", "last_name": "Kip", "grade_level": "Grade 2"},
    ])
    assert r.status_code == 201
    assert r.json()["created"] == 2

    r = as_admin.get("/api/students/")
    numbers = {s["first_name"]: s["admission_number"] for s in r.json()}
    assert numbers["Amina"].startswith("BNS-")
    assert numbers["Brian"].startswith("BNS-")
    assert numbers["Amina"] != numbers["Brian"]


def test_bulk_import_forbidden_for_accountant(as_accountant):
    r = as_accountant.post("/api/students/bulk", json=[
        {"first_name": "X", "last_name": "Y", "grade_level": "Grade 1"}])
    assert r.status_code == 403


def test_backdated_payment_keeps_paper_date(as_admin, db_session, sample_student):
    year = datetime.now().year
    db_session.add(models.FeeStructure(
        grade_level="Grade 1", term="Term 1", fee_type="Tuition",
        amount=1000, academic_year=year))
    db_session.commit()

    r = as_admin.post("/api/fees/", json={
        "student_id": sample_student.id, "amount": 500, "payment_type": "Tuition",
        "term": "Term 1", "current_term": "Term 1",
        "payment_date": f"{year}-02-10"})
    assert r.status_code == 200
    assert r.json()["payment_date"].startswith(f"{year}-02-10")

    # Without a date, the server stamps "now"
    r = as_admin.post("/api/fees/", json={
        "student_id": sample_student.id, "amount": 100, "payment_type": "Tuition",
        "term": "Term 1", "current_term": "Term 1"})
    assert r.status_code == 200
    assert not r.json()["payment_date"].startswith(f"{year}-02-10")
