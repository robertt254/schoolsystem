from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models, schemas, auth
from audit import log_action
from constants import TERM_ORDER
from typing import List, Optional

router = APIRouter(prefix="/api/exams", tags=["Exams"])

WRITE_ROLES = {"admin", "principal", "teacher", "senior_teacher"}


def _was_enrolled_for_term(student, term: str, academic_year: int) -> bool:
    """Mid-year joiners didn't sit exams from before they joined the school —
    mirrors fees._owes_term's admission_term/admission_year logic. Unlike
    fees.py (which always compares against "now"), this compares against the
    requested academic_year: exam records are routinely viewed for past
    years, not just the current one."""
    admission_year = getattr(student, "admission_year", None)
    if admission_year is None or admission_year < academic_year:
        return True
    if admission_year > academic_year:
        return False
    admission_term = getattr(student, "admission_term", None) or "Term 1"
    return TERM_ORDER.get(term, 1) >= TERM_ORDER.get(admission_term, 1)


@router.post("/bulk", status_code=201)
def record_exam_results(
    payload: schemas.ExamBulkCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Batch-fetch valid students and existing results once — avoids two
    # queries per entry in the loop below.
    entry_ids = [e.student_id for e in payload.results]
    valid_students = {
        s.id: s
        for s in db.query(models.Student).filter(
            models.Student.id.in_(entry_ids),
            models.Student.is_deleted == False,
        ).all()
    }
    existing_by_student = {
        r.student_id: r
        for r in db.query(models.ExamResult).filter(
            models.ExamResult.student_id.in_(entry_ids),
            models.ExamResult.subject == payload.subject,
            models.ExamResult.exam_type == payload.exam_type,
            models.ExamResult.term == payload.term,
            models.ExamResult.academic_year == payload.academic_year,
        ).all()
    }

    upserted = 0
    skipped_ineligible = 0
    for entry in payload.results:
        student = valid_students.get(entry.student_id)
        if not student:
            continue
        # A mid-year joiner has nothing to record for a term before they
        # were admitted — reject rather than silently create a mark for an
        # exam the student never sat.
        if not _was_enrolled_for_term(student, payload.term, payload.academic_year):
            skipped_ineligible += 1
            continue

        existing = existing_by_student.get(entry.student_id)

        if existing:
            existing.marks = entry.marks
            existing.max_marks = entry.max_marks
            existing.recorded_by = current_user.name
            log_action(db, current_user.id, "UPDATE", "exam_result", existing.id,
                       {"subject": payload.subject, "marks": float(entry.marks)})
        else:
            new_result = models.ExamResult(
                student_id=entry.student_id,
                grade_level=payload.grade_level,
                subject=payload.subject,
                exam_type=payload.exam_type,
                marks=entry.marks,
                max_marks=entry.max_marks,
                term=payload.term,
                academic_year=payload.academic_year,
                recorded_by=current_user.name,
            )
            db.add(new_result)
            log_action(db, current_user.id, "CREATE", "exam_result", None,
                       {"subject": payload.subject, "student_id": entry.student_id})
        upserted += 1

    db.commit()
    return {"saved": upserted, "skipped_ineligible": skipped_ineligible}


@router.get("/grade/{grade_level}/{term}")
def get_grade_results(
    grade_level: str,
    term: str,
    academic_year: int = Query(...),
    exam_type: str = Query(
        ..., description="Opener | MidTerm | EndTerm — a merit list is always scoped to exactly one exam; "
                          "results are stored separately per exam and must never be blended together."
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    students = db.query(models.Student).filter(
        models.Student.grade_level == grade_level,
        models.Student.is_deleted == False,
        models.Student.status == "Active",
    ).order_by(models.Student.last_name, models.Student.first_name).all()
    # Mid-year joiners weren't enrolled for terms before their admission —
    # exclude them from that term's merit list rather than showing them with
    # every subject blank and Total 0 (indistinguishable from a student who
    # actually sat every paper and scored zero).
    students = [s for s in students if _was_enrolled_for_term(s, term, academic_year)]

    results = db.query(models.ExamResult).filter(
        models.ExamResult.grade_level == grade_level,
        models.ExamResult.term == term,
        models.ExamResult.academic_year == academic_year,
        models.ExamResult.exam_type == exam_type,
    ).all()

    result_map = {}
    for r in results:
        result_map.setdefault(r.student_id, {})[r.subject] = {
            "marks": float(r.marks),
            "max_marks": r.max_marks,
        }

    subjects = sorted({r.subject for r in results})

    rows = []
    for s in students:
        subj_scores = result_map.get(s.id, {})
        total = sum(v["marks"] for v in subj_scores.values())
        max_total = sum(v["max_marks"] for v in subj_scores.values())
        rows.append({
            "student_id": s.id,
            "student_name": f"{s.first_name} {s.last_name}",
            "admission_number": s.admission_number,
            "scores": subj_scores,
            "total_marks": round(total, 1),
            "max_marks": max_total,
            "percentage": round(total / max_total * 100, 1) if max_total > 0 else None,
        })

    rows.sort(key=lambda r: r["total_marks"], reverse=True)
    for i, row in enumerate(rows):
        row["position"] = i + 1

    return {"subjects": subjects, "students": rows}


@router.get("/grade/{grade_level}/{term}/detailed")
def get_grade_results_detailed(
    grade_level: str,
    term: str,
    academic_year: int = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Every exam-type result for every eligible student in a grade/term, as a
    flat per-student list — unlike get_grade_results (a ranked merit list,
    always scoped to exactly one exam type), this is for whole-class report
    card printing, where a student's Opener/Mid Term/End Term marks should
    all show, not be collapsed into one exam."""
    if current_user.role not in {"admin", "principal", "senior_teacher", "teacher"}:
        raise HTTPException(status_code=403, detail="Not authorized")

    students = db.query(models.Student).filter(
        models.Student.grade_level == grade_level,
        models.Student.is_deleted == False,
        models.Student.status == "Active",
    ).order_by(models.Student.last_name, models.Student.first_name).all()
    students = [s for s in students if _was_enrolled_for_term(s, term, academic_year)]

    results = db.query(models.ExamResult).filter(
        models.ExamResult.grade_level == grade_level,
        models.ExamResult.term == term,
        models.ExamResult.academic_year == academic_year,
    ).all()

    by_student: dict = {}
    for r in results:
        by_student.setdefault(r.student_id, []).append({
            "subject": r.subject,
            "exam_type": r.exam_type,
            "marks": float(r.marks),
            "max_marks": r.max_marks,
        })

    return {
        "students": [
            {
                "student_id": s.id,
                "student_name": f"{s.first_name} {s.last_name}",
                "admission_number": s.admission_number,
                "results": by_student.get(s.id, []),
            }
            for s in students
        ]
    }


@router.get("/student/{student_id}")
def get_student_results(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    student = db.query(models.Student).filter(
        models.Student.id == student_id,
        models.Student.is_deleted == False,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    results = db.query(models.ExamResult).filter(
        models.ExamResult.student_id == student_id,
    ).order_by(
        models.ExamResult.academic_year.desc(),
        models.ExamResult.term,
        models.ExamResult.exam_type,
        models.ExamResult.subject,
    ).all()

    return [
        {
            "id": r.id,
            "subject": r.subject,
            "exam_type": r.exam_type,
            "marks": float(r.marks),
            "max_marks": r.max_marks,
            "term": r.term,
            "academic_year": r.academic_year,
        }
        for r in results
    ]


@router.get("/performance-summary")
def performance_summary(
    academic_year: Optional[str] = Query(None),
    term: Optional[str] = Query(None),
    grade_level: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = db.query(
        models.ExamResult.grade_level,
        models.ExamResult.subject,
        models.ExamResult.exam_type,
        func.avg(models.ExamResult.marks).label("avg_score"),
        func.max(models.ExamResult.marks).label("highest"),
        func.min(models.ExamResult.marks).label("lowest"),
        func.count(models.ExamResult.id).label("num_students"),
    )
    if academic_year:
        q = q.filter(models.ExamResult.academic_year == academic_year)
    if term:
        q = q.filter(models.ExamResult.term == term)
    if grade_level:
        q = q.filter(models.ExamResult.grade_level == grade_level)
    rows = q.group_by(
        models.ExamResult.grade_level,
        models.ExamResult.subject,
        models.ExamResult.exam_type,
    ).order_by(
        models.ExamResult.grade_level,
        models.ExamResult.subject,
    ).all()
    return [
        {
            "grade_level": r.grade_level,
            "subject": r.subject,
            "exam_type": r.exam_type,
            "avg_score": round(float(r.avg_score or 0), 1),
            "highest": round(float(r.highest or 0), 1),
            "lowest": round(float(r.lowest or 0), 1),
            "num_students": r.num_students,
        }
        for r in rows
    ]


@router.delete("/{result_id}", status_code=204)
def delete_result(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized")
    row = db.query(models.ExamResult).filter(models.ExamResult.id == result_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Result not found")
    log_action(db, current_user.id, "DELETE", "exam_result", result_id)
    db.delete(row)
    db.commit()
