from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, case
from database import get_db
import models
import schemas
import auth
from audit import log_action
from constants import CBC_GRADES
from fees import _expected_fee_for_student, _expected_fee_map, _expected_from_map_for_student
from activities import ensure_compulsory_enrollment

router = APIRouter(prefix="/api/students", tags=["Students"])

WRITE_ROLES = {"admin", "principal", "secretary"}


@router.get("/classes/summary")
def get_classes_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return per-grade headcount, present-today count, and gender split."""
    today = datetime.now().date()

    # Single query for all active students
    all_students = db.query(models.Student).filter(
        models.Student.is_deleted == False,
        models.Student.status == "Active",
    ).all()
    if not all_students:
        return []

    all_ids = [s.id for s in all_students]

    # Single query for today's present set
    present_set = {
        row.student_id
        for row in db.query(models.Attendance.student_id).filter(
            models.Attendance.student_id.in_(all_ids),
            models.Attendance.date == today,
            models.Attendance.is_present,
        ).all()
    }

    # Group in Python
    from collections import defaultdict
    by_grade: dict = defaultdict(list)
    for s in all_students:
        by_grade[s.grade_level].append(s)

    result = []
    for grade in CBC_GRADES:
        students = by_grade.get(grade, [])
        if not students:
            continue
        male = sum(1 for s in students if (s.gender or "").lower() == "male")
        female = sum(1 for s in students if (s.gender or "").lower() == "female")
        result.append({
            "grade_level": grade,
            "total": len(students),
            "present_today": sum(1 for s in students if s.id in present_set),
            "male": male,
            "female": female,
            "other": len(students) - male - female,
        })
    return result


@router.get("/classes/{grade}")
def get_class_roster(
    grade: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return all students in a grade with attendance % and current fee balance."""
    students = db.query(models.Student).filter(
        models.Student.grade_level == grade,
        models.Student.is_deleted == False,
    ).order_by(models.Student.last_name).all()
    if not students:
        return []

    ids = [s.id for s in students]

    # Batch: attendance counts per student
    att_rows = db.query(
        models.Attendance.student_id,
        func.count(models.Attendance.id).label("total"),
        func.sum(case((models.Attendance.is_present, 1), else_=0)).label("present"),
    ).filter(models.Attendance.student_id.in_(ids)).group_by(models.Attendance.student_id).all()
    att = {r.student_id: (int(r.total), int(r.present)) for r in att_rows}

    # Batch: fee structures for the year, using the same shared helper the
    # finance module uses — avoids duplicating the mid-year-joiner logic here.
    fee_map = _expected_fee_map(db)
    def annual_expected_for(s) -> float:
        return sum(_expected_from_map_for_student(fee_map, s, t) for t in ["Term 1", "Term 2", "Term 3"])

    # Batch: total TUITION paid per student (all terms) — activity IS NULL
    # excludes Transport/Co-curricular/Other payments, which aren't tuition
    # and would otherwise inflate this against a tuition-only expected figure.
    paid_rows = db.query(
        models.FeePayment.student_id,
        func.sum(models.FeePayment.amount).label("total"),
    ).filter(
        models.FeePayment.student_id.in_(ids),
        models.FeePayment.activity.is_(None),
    ).group_by(models.FeePayment.student_id).all()
    paid = {r.student_id: float(r.total) for r in paid_rows}

    roster = []
    for s in students:
        total_days, days_present = att.get(s.id, (0, 0))
        att_pct = round(days_present / total_days * 100) if total_days > 0 else None
        total_paid = paid.get(s.id, 0.0)
        roster.append({
            "id": s.id,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "admission_number": s.admission_number,
            "gender": s.gender,
            "date_of_birth": s.date_of_birth.isoformat() if s.date_of_birth else None,
            "status": s.status,
            "attendance_pct": att_pct,
            "fee_balance": round(annual_expected_for(s) - total_paid, 2),
        })
    return roster


def _generate_admission_number(db: Session) -> str:
    last = (
        db.query(models.Student)
        .filter(models.Student.admission_number.like("BNS-%"))
        .with_for_update()
        .order_by(models.Student.id.desc())
        .first()
    )
    if last and last.admission_number:
        try:
            seq = int(last.admission_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"BNS-{seq:04d}"


@router.post("/", response_model=schemas.StudentResponse)
def create_student(
    student: schemas.StudentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to admit students")

    # Admission numbers are always system-generated: sequential, unique and
    # immutable once assigned. Any client-supplied value is ignored.
    admission_number = _generate_admission_number(db)
    while db.query(models.Student).filter(
        models.Student.admission_number == admission_number
    ).first():
        seq = int(admission_number.split("-")[-1]) + 1
        admission_number = f"BNS-{seq:04d}"

    data = student.model_dump()
    data["admission_number"] = admission_number
    # Default: owes the full current year unless a joining term was given
    if not data.get("admission_year"):
        data["admission_year"] = datetime.now().year
    if not data.get("admission_term"):
        data["admission_term"] = "Term 1"
    new_student = models.Student(**data)
    db.add(new_student)
    db.flush()
    log_action(db, current_user.id, "CREATE", "student", new_student.id,
               {"admission_number": admission_number,
                "first_name": new_student.first_name, "last_name": new_student.last_name})
    # French is compulsory from Grade 1 onward — subscribe automatically.
    ensure_compulsory_enrollment(db, new_student, data["admission_year"],
                                  data["admission_term"], current_user.name)
    db.commit()
    db.refresh(new_student)
    return new_student


@router.post("/bulk", status_code=201)
def bulk_import_students(
    students: list[schemas.StudentCreate],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Register many students in one call — for migrating paper/spreadsheet
    records. Admission numbers are system-generated per row, same as single
    admissions."""
    if current_user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to admit students")
    if len(students) > 500:
        raise HTTPException(status_code=400, detail="Bulk limit is 500 students per request")

    created = 0
    for entry in students:
        admission_number = _generate_admission_number(db)
        while db.query(models.Student).filter(
            models.Student.admission_number == admission_number
        ).first():
            seq = int(admission_number.split("-")[-1]) + 1
            admission_number = f"BNS-{seq:04d}"

        data = entry.model_dump()
        data["admission_number"] = admission_number
        if not data.get("admission_year"):
            data["admission_year"] = datetime.now().year
        if not data.get("admission_term"):
            data["admission_term"] = "Term 1"
        new_student = models.Student(**data)
        db.add(new_student)
        db.flush()
        log_action(db, current_user.id, "CREATE", "student", new_student.id,
                   {"admission_number": admission_number, "bulk_import": True,
                    "first_name": new_student.first_name, "last_name": new_student.last_name})
        ensure_compulsory_enrollment(db, new_student, data["admission_year"],
                                      data["admission_term"], current_user.name)
        created += 1

    db.commit()
    return {"created": created}


@router.get("/", response_model=list[schemas.StudentResponse])
def get_all_students(
    skip: int = 0,
    limit: int = 200,
    search: Optional[str] = Query(None, description="Search by name or admission number"),
    grade: Optional[str] = Query(None, description="Filter by grade level"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = db.query(models.Student).filter(models.Student.is_deleted == False)
    if search:
        like = f"%{search}%"
        q = q.filter(
            or_(
                models.Student.first_name.ilike(like),
                models.Student.last_name.ilike(like),
                models.Student.admission_number.ilike(like),
            )
        )
    if grade:
        q = q.filter(models.Student.grade_level == grade)
    return q.order_by(models.Student.last_name).offset(skip).limit(limit).all()


@router.get("/archived", response_model=list[schemas.StudentResponse])
def get_archived_students(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admins and the principal can view archived records")
    return db.query(models.Student).filter(models.Student.is_deleted).all()


# NOTE: must be registered before GET /{student_id}, which would otherwise
# swallow "enrollment-summary" as a student id and return 422.
@router.get("/enrollment-summary")
def enrollment_summary(
    academic_year: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = db.query(models.Student.grade_level, func.count(models.Student.id).label("count")).filter(
        models.Student.is_deleted == False,
        models.Student.status == "Active",
    )
    rows = q.group_by(models.Student.grade_level).all()
    grade_order = ["Play Group","PP1","PP2","Grade 1","Grade 2","Grade 3","Grade 4","Grade 5","Grade 6"]
    order_map = {g: i for i, g in enumerate(grade_order)}
    result = [{"grade_level": r.grade_level, "count": r.count} for r in rows]
    result.sort(key=lambda x: order_map.get(x["grade_level"], 99))
    return result


@router.get("/{student_id}/profile")
def get_student_profile(
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

    # Attendance rate
    total_days = db.query(func.count(models.Attendance.id)).filter(
        models.Attendance.student_id == student_id
    ).scalar() or 0
    days_present = db.query(func.count(models.Attendance.id)).filter(
        models.Attendance.student_id == student_id,
        models.Attendance.is_present,
    ).scalar() or 0
    att_pct = round(days_present / total_days * 100) if total_days > 0 else 100

    # Annual fee balance (all three terms this academic year) — nothing for
    # terms before a mid-year joiner's admission term.
    terms = ["Term 1", "Term 2", "Term 3"]
    total_expected = round(sum(_expected_fee_for_student(db, student, t) for t in terms), 2)

    total_paid = float(
        db.query(func.sum(models.FeePayment.amount)).filter(
            models.FeePayment.student_id == student_id,
            models.FeePayment.activity.is_(None),
        ).scalar() or 0
    )

    # All assessments ordered by term
    assessments = db.query(models.Assessment).filter(
        models.Assessment.student_id == student_id
    ).order_by(models.Assessment.term, models.Assessment.learning_area).all()

    # Last 15 fee payments
    payments = db.query(models.FeePayment).filter(
        models.FeePayment.student_id == student_id
    ).order_by(models.FeePayment.payment_date.desc()).limit(15).all()

    return {
        "student": schemas.StudentResponse.model_validate(student),
        "attendance_percentage": att_pct,
        "total_days": total_days,
        "days_present": days_present,
        "fee_balance": round(total_expected - total_paid, 2),
        "total_paid": round(total_paid, 2),
        "assessments": [
            {"id": a.id, "term": a.term, "learning_area": a.learning_area,
             "score": a.score, "remarks": a.remarks}
            for a in assessments
        ],
        "recent_payments": [
            {"id": p.id, "receipt_number": p.receipt_number,
             "amount": float(p.amount), "payment_type": p.payment_type,
             "term": p.term, "payment_date": p.payment_date.isoformat(),
             "recorded_by": p.recorded_by}
            for p in payments
        ],
    }


@router.get("/{student_id}", response_model=schemas.StudentResponse)
def get_student(
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
    return student


@router.put("/{student_id}", response_model=schemas.StudentResponse)
def update_student(
    student_id: int,
    student_update: schemas.StudentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to update student records")

    db_student = db.query(models.Student).filter(
        models.Student.id == student_id,
        models.Student.is_deleted == False,
    ).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")

    update_data = student_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_student, key, value)

    log_action(db, current_user.id, "UPDATE", "student", student_id, update_data)
    db.commit()
    db.refresh(db_student)
    return db_student


@router.delete("/{student_id}")
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admins and the principal can archive student records")

    db_student = db.query(models.Student).filter(
        models.Student.id == student_id,
        models.Student.is_deleted == False,
    ).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")

    db_student.is_deleted = True
    db_student.status = "inactive"
    log_action(db, current_user.id, "DELETE", "student", student_id,
               {"admission_number": db_student.admission_number})
    db.commit()
    return {"message": f"Student {student_id} archived. Record preserved for audit purposes."}


@router.patch("/{student_id}/deactivate")
def deactivate_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Mark a student as Transferred (fee-cleared deactivation).
    Records are preserved. Requires all outstanding fees to be settled first.
    """
    if current_user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to deactivate students")

    db_student = db.query(models.Student).filter(
        models.Student.id == student_id,
        models.Student.is_deleted == False,
        models.Student.status == "Active",
    ).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Active student not found")

    # Check outstanding TUITION balance across all terms
    total_paid = float(
        db.query(func.sum(models.FeePayment.amount))
        .filter(models.FeePayment.student_id == student_id,
                models.FeePayment.activity.is_(None))
        .scalar() or 0
    )
    total_expected = sum(
        _expected_fee_for_student(db, db_student, t)
        for t in ["Term 1", "Term 2", "Term 3"]
    )
    outstanding = round(total_expected - total_paid, 2)
    if outstanding > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Student has an outstanding fee balance of KES {outstanding:,.2f}. "
                   "All fees must be settled before deactivation.",
        )

    db_student.status = "Transferred"
    log_action(db, current_user.id, "UPDATE", "student", student_id,
               {"status": "Transferred", "admission_number": db_student.admission_number})
    db.commit()
    return {"message": f"{db_student.first_name} {db_student.last_name} has been deactivated (Transferred). Records retained."}


GRADE_PROGRESSION = {
    "Play Group": "PP1", "PP1": "PP2", "PP2": "Grade 1",
    "Grade 1": "Grade 2", "Grade 2": "Grade 3", "Grade 3": "Grade 4",
    "Grade 4": "Grade 5", "Grade 5": "Grade 6", "Grade 6": None,
}


def promotion_window_open(db: Session, today=None) -> bool:
    """Promotions happen only at the END of the academic year: after Term 3
    closes and before the next year's Term 1 begins (the long holiday)."""
    from events import _term_ranges
    today = today or datetime.now().date()
    ranges, _ = _term_ranges(db, today.year)
    term1 = ranges.get("Term 1")
    term3 = ranges.get("Term 3")
    after_year_end = bool(term3) and today > term3[1]
    before_year_start = bool(term1) and today < term1[0]
    return after_year_end or before_year_start


def _require_promotion_window(db: Session):
    if not promotion_window_open(db):
        raise HTTPException(
            status_code=400,
            detail="Promotions are only allowed at the end of the academic year "
                   "(after Term 3 ends and before the new year's Term 1 begins).",
        )


@router.post("/promote")
def promote_students(
    payload: schemas.PromotionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admin or principal can promote students")
    _require_promotion_window(db)

    # Single query for the whole batch — avoids an N+1 per student id
    students = db.query(models.Student).filter(
        models.Student.id.in_(payload.student_ids),
        models.Student.is_deleted == False,
    ).all()

    promoted, graduated = 0, 0
    for student in students:
        sid = student.id
        if payload.to_grade is None:
            next_grade = GRADE_PROGRESSION.get(student.grade_level)
        else:
            next_grade = payload.to_grade

        if next_grade is None:
            student.status = "Graduated"
            graduated += 1
            log_action(db, current_user.id, "UPDATE", "student", sid,
                       {"from": student.grade_level, "status": "Graduated"})
        else:
            log_action(db, current_user.id, "UPDATE", "student", sid,
                       {"from": student.grade_level, "to": next_grade})
            student.grade_level = next_grade
            promoted += 1
            # A PP2 -> Grade 1 promotion crosses into compulsory-French
            # territory — subscribe them for the new academic year, same as
            # a fresh Grade 1+ admission.
            ensure_compulsory_enrollment(db, student, datetime.now().year, "Term 1", current_user.name)

    db.commit()
    return {"promoted": promoted, "graduated": graduated}


@router.post("/year-transition")
def year_transition(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Promote ALL active students to next grade; Grade 6 → Graduated."""
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admin or principal can run year transition")
    _require_promotion_window(db)

    students = db.query(models.Student).filter(
        models.Student.is_deleted == False,
        models.Student.status == "Active",
    ).all()

    promoted, graduated = 0, 0
    for student in students:
        next_grade = GRADE_PROGRESSION.get(student.grade_level)
        if next_grade is None:
            student.status = "Graduated"
            graduated += 1
        else:
            student.grade_level = next_grade
            promoted += 1
        log_action(db, current_user.id, "UPDATE", "student", student.id,
                   {"year_transition": True,
                    "from": student.grade_level if next_grade else student.grade_level,
                    "to": next_grade or "Graduated"})

    db.commit()
    return {"promoted": promoted, "graduated": graduated, "total": promoted + graduated}


@router.post("/{student_id}/restore", response_model=schemas.StudentResponse)
def restore_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admins and the principal can restore student records")

    db_student = db.query(models.Student).filter(
        models.Student.id == student_id,
        models.Student.is_deleted,
    ).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Archived student not found")

    db_student.is_deleted = False
    db_student.status = "Active"
    log_action(db, current_user.id, "UPDATE", "student", student_id, {"restored": True})
    db.commit()
    db.refresh(db_student)
    return db_student
