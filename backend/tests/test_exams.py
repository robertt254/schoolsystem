"""Exam records: each exam type is stored and viewed independently, and a
mid-year joiner is excluded from exams that predate their admission —
mirrors the fee engine's existing admission_term/admission_year logic."""
from datetime import datetime
import models


def _record(client, grade, term, exam_type, subject, year, results):
    return client.post("/api/exams/bulk", json={
        "grade_level": grade, "term": term, "exam_type": exam_type,
        "subject": subject, "academic_year": year, "results": results,
    })


def test_exam_type_is_required_for_merit_list(as_admin):
    r = as_admin.get("/api/exams/grade/Grade 1/Term 1", params={"academic_year": 2026})
    assert r.status_code == 422  # exam_type must be provided


def test_different_exam_types_do_not_clobber_each_other(as_admin, sample_student):
    year = datetime.now().year
    r = _record(as_admin, "Grade 1", "Term 1", "Opener", "Math", year,
                [{"student_id": sample_student.id, "marks": 60, "max_marks": 100}])
    assert r.status_code == 201
    r = _record(as_admin, "Grade 1", "Term 1", "MidTerm", "Math", year,
                [{"student_id": sample_student.id, "marks": 85, "max_marks": 100}])
    assert r.status_code == 201

    opener = as_admin.get("/api/exams/grade/Grade 1/Term 1",
                           params={"academic_year": year, "exam_type": "Opener"}).json()
    midterm = as_admin.get("/api/exams/grade/Grade 1/Term 1",
                            params={"academic_year": year, "exam_type": "MidTerm"}).json()

    # Each merit list shows only its own exam's marks — neither overwrote the other.
    assert opener["students"][0]["scores"]["Math"]["marks"] == 60.0
    assert midterm["students"][0]["scores"]["Math"]["marks"] == 85.0


def test_detailed_endpoint_returns_every_exam_type_per_student(as_admin, sample_student):
    year = datetime.now().year
    _record(as_admin, "Grade 1", "Term 1", "Opener", "Math", year,
            [{"student_id": sample_student.id, "marks": 60, "max_marks": 100}])
    _record(as_admin, "Grade 1", "Term 1", "EndTerm", "Math", year,
            [{"student_id": sample_student.id, "marks": 90, "max_marks": 100}])

    r = as_admin.get("/api/exams/grade/Grade 1/Term 1/detailed", params={"academic_year": year})
    assert r.status_code == 200
    rows = r.json()["students"][0]["results"]
    exam_types = sorted(row["exam_type"] for row in rows)
    assert exam_types == ["EndTerm", "Opener"]


def test_midyear_joiner_excluded_from_earlier_term_merit_list(as_admin, db_session):
    year = datetime.now().year
    late_joiner = models.Student(
        first_name="Late", last_name="Joiner", admission_number="BNS-0099",
        grade_level="Grade 1", status="Active",
        admission_year=year, admission_term="Term 2",
    )
    db_session.add(late_joiner)
    db_session.commit()
    db_session.refresh(late_joiner)

    # Term 1 predates their admission — they must not appear at all.
    r = as_admin.get("/api/exams/grade/Grade 1/Term 1",
                      params={"academic_year": year, "exam_type": "Opener"})
    ids = [s["student_id"] for s in r.json()["students"]]
    assert late_joiner.id not in ids

    # Term 2 is when they joined — they should appear (with no marks yet).
    r = as_admin.get("/api/exams/grade/Grade 1/Term 2",
                      params={"academic_year": year, "exam_type": "Opener"})
    ids = [s["student_id"] for s in r.json()["students"]]
    assert late_joiner.id in ids


def test_midyear_joiner_excluded_from_entry_sheet_detailed_view(as_admin, db_session):
    year = datetime.now().year
    late_joiner = models.Student(
        first_name="Late", last_name="Joiner2", admission_number="BNS-0098",
        grade_level="Grade 1", status="Active",
        admission_year=year, admission_term="Term 3",
    )
    db_session.add(late_joiner)
    db_session.commit()

    r = as_admin.get("/api/exams/grade/Grade 1/Term 1/detailed", params={"academic_year": year})
    ids = [s["student_id"] for s in r.json()["students"]]
    assert late_joiner.id not in ids


def test_bulk_save_skips_marks_for_a_term_before_admission(as_admin, db_session):
    year = datetime.now().year
    late_joiner = models.Student(
        first_name="Late", last_name="Joiner3", admission_number="BNS-0097",
        grade_level="Grade 1", status="Active",
        admission_year=year, admission_term="Term 2",
    )
    db_session.add(late_joiner)
    db_session.commit()
    db_session.refresh(late_joiner)

    r = _record(as_admin, "Grade 1", "Term 1", "Opener", "Math", year,
                [{"student_id": late_joiner.id, "marks": 70, "max_marks": 100}])
    assert r.status_code == 201
    body = r.json()
    assert body["saved"] == 0
    assert body["skipped_ineligible"] == 1

    # Nothing was actually recorded.
    stored = db_session.query(models.ExamResult).filter(
        models.ExamResult.student_id == late_joiner.id
    ).count()
    assert stored == 0
