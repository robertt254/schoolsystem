from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth
from typing import List, Optional
from audit import log_action

router = APIRouter(prefix="/api/academics", tags=["Academics"])


@router.post("/scores")
def record_scores(
    scores: List[schemas.AssessmentCreate],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"teacher", "senior_teacher", "admin", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized to alter academic records")

    student_ids = {s.student_id for s in scores}
    existing_students = {
        s.id
        for s in db.query(models.Student.id).filter(
            models.Student.id.in_(student_ids),
            models.Student.is_deleted == False,
        ).all()
    }
    missing = student_ids - existing_students
    if missing:
        raise HTTPException(status_code=404, detail=f"Student IDs not found: {sorted(missing)}")

    for score in scores:
        existing = db.query(models.Assessment).filter(
            models.Assessment.student_id == score.student_id,
            models.Assessment.academic_year == score.academic_year,
            models.Assessment.term == score.term,
            models.Assessment.learning_area == score.learning_area,
            models.Assessment.strand == score.strand,
        ).first()

        if existing:
            existing.score = score.score
            existing.remarks = score.remarks
            log_action(db, current_user.id, "UPDATE", "assessment", existing.id,
                       {"student_id": score.student_id, "learning_area": score.learning_area,
                        "strand": score.strand, "score": score.score})
        else:
            new_score = models.Assessment(**score.model_dump())
            db.add(new_score)
            db.flush()
            log_action(db, current_user.id, "CREATE", "assessment", new_score.id,
                       {"student_id": score.student_id, "learning_area": score.learning_area,
                        "strand": score.strand, "score": score.score})

    db.commit()
    return {"message": "Academic scores updated successfully"}


@router.get("/grade/{grade}/{term}")
def get_grade_assessments(
    grade: str,
    term: str,
    academic_year: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return all students in a grade with their existing strand scores for the given term."""
    if current_user.role not in {"teacher", "senior_teacher", "admin", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized")

    students = (
        db.query(models.Student)
        .filter(models.Student.grade_level == grade, models.Student.is_deleted == False)
        .order_by(models.Student.last_name)
        .all()
    )

    result = []
    for s in students:
        q = db.query(models.Assessment).filter(
            models.Assessment.student_id == s.id,
            models.Assessment.term == term,
        )
        if academic_year:
            q = q.filter(models.Assessment.academic_year == academic_year)
        assessments = q.all()

        # scores[learning_area][strand] = {score, remarks}
        scores: dict = {}
        for a in assessments:
            if a.learning_area not in scores:
                scores[a.learning_area] = {}
            scores[a.learning_area][a.strand] = {
                "score": a.score,
                "remarks": a.remarks,
            }

        result.append({
            "student_id": s.id,
            "student_name": f"{s.first_name} {s.last_name}",
            "admission_number": s.admission_number,
            "scores": scores,
        })
    return result


@router.get("/report-card/{student_id}/{term}")
def generate_report_card(
    student_id: int,
    term: str,
    academic_year: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    student = db.query(models.Student).filter(
        models.Student.id == student_id,
        models.Student.is_deleted == False,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    q = db.query(models.Assessment).filter(
        models.Assessment.student_id == student_id,
        models.Assessment.term == term,
    )
    if academic_year:
        q = q.filter(models.Assessment.academic_year == academic_year)
    assessments = q.all()

    # Group by learning_area → {strands: {strand: score}, remarks: str}
    areas: dict = {}
    for a in assessments:
        if a.learning_area not in areas:
            areas[a.learning_area] = {"strands": {}, "remarks": None}
        areas[a.learning_area]["strands"][a.strand] = a.score
        if a.remarks:
            areas[a.learning_area]["remarks"] = a.remarks

    results = [
        {
            "learning_area": area,
            "strands": data["strands"],
            "remarks": data["remarks"],
        }
        for area, data in areas.items()
    ]

    return {
        "student_name": f"{student.first_name} {student.last_name}",
        "admission_number": student.admission_number,
        "grade_level": student.grade_level,
        "term": term,
        "academic_year": academic_year or "",
        "results": results,
    }
