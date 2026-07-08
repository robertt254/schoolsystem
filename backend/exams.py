from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models, schemas, auth
from audit import log_action
from typing import List, Optional

router = APIRouter(prefix="/api/exams", tags=["Exams"])

WRITE_ROLES = {"admin", "principal", "teacher", "senior_teacher"}


@router.post("/bulk", status_code=201)
def record_exam_results(
    payload: schemas.ExamBulkCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")

    upserted = 0
    for entry in payload.results:
        student = db.query(models.Student).filter(
            models.Student.id == entry.student_id,
            models.Student.is_deleted == False,
        ).first()
        if not student:
            continue

        existing = db.query(models.ExamResult).filter(
            models.ExamResult.student_id == entry.student_id,
            models.ExamResult.subject == payload.subject,
            models.ExamResult.exam_type == payload.exam_type,
            models.ExamResult.term == payload.term,
            models.ExamResult.academic_year == payload.academic_year,
        ).first()

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
    return {"saved": upserted}


@router.get("/grade/{grade_level}/{term}")
def get_grade_results(
    grade_level: str,
    term: str,
    academic_year: int = Query(...),
    exam_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    students = db.query(models.Student).filter(
        models.Student.grade_level == grade_level,
        models.Student.is_deleted == False,
        models.Student.status == "Active",
    ).order_by(models.Student.last_name, models.Student.first_name).all()

    q = db.query(models.ExamResult).filter(
        models.ExamResult.grade_level == grade_level,
        models.ExamResult.term == term,
        models.ExamResult.academic_year == academic_year,
    )
    if exam_type:
        q = q.filter(models.ExamResult.exam_type == exam_type)
    results = q.all()

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
