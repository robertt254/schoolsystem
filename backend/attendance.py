from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from database import get_db
import models, schemas, auth
from audit import log_action
from notifications import notify_absence
from typing import List
from datetime import date

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])

MARK_ROLES = {"teacher", "senior_teacher", "principal", "admin", "secretary"}

GRADE_ORDER = [
    "Play Group", "PP1", "PP2",
    "Grade 1", "Grade 2", "Grade 3",
    "Grade 4", "Grade 5", "Grade 6",
]


@router.post("/bulk")
def log_bulk_attendance(
    records: List[schemas.AttendanceCreate],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in MARK_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to mark attendance")

    student_ids = [r.student_id for r in records]
    existing_students = {
        s.id
        for s in db.query(models.Student.id).filter(
            models.Student.id.in_(student_ids),
            models.Student.is_deleted == False,
        ).all()
    }
    missing = set(student_ids) - existing_students
    if missing:
        raise HTTPException(status_code=404, detail=f"Student IDs not found: {sorted(missing)}")

    today = date.today()
    existing_records = {
        att.student_id: att
        for att in db.query(models.Attendance).filter(
            and_(
                models.Attendance.student_id.in_(student_ids),
                models.Attendance.date == today,
            )
        ).all()
    }

    for record in records:
        if record.student_id in existing_records:
            existing_records[record.student_id].is_present = record.is_present
            existing_records[record.student_id].remarks = record.remarks
        else:
            db.add(models.Attendance(**record.model_dump()))

    log_action(db, current_user.id, "CREATE", "attendance", None,
               {"date": str(today), "count": len(records)})
    db.commit()

    # Send absence SMS for students marked absent (fire-and-forget)
    absent_ids = [r.student_id for r in records if not r.is_present]
    if absent_ids:
        absent_students = db.query(models.Student).filter(
            models.Student.id.in_(absent_ids),
            models.Student.guardian_phone.isnot(None),
        ).all()
        date_str = today.strftime("%d %b %Y")
        for student in absent_students:
            name = f"{student.first_name} {student.last_name}"
            background_tasks.add_task(notify_absence, name, student.guardian_phone, date_str)
            if student.guardian2_phone:
                background_tasks.add_task(notify_absence, name, student.guardian2_phone, date_str)

    return {"message": "Attendance updated successfully"}


@router.get("/student/{student_id}")
def get_student_attendance(
    student_id: int,
    limit: int = 60,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    student = db.query(models.Student).filter(
        models.Student.id == student_id,
        models.Student.is_deleted == False,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    total = db.query(func.count(models.Attendance.id)).filter(
        models.Attendance.student_id == student_id
    ).scalar() or 0
    present = db.query(func.count(models.Attendance.id)).filter(
        models.Attendance.student_id == student_id,
        models.Attendance.is_present == True,
    ).scalar() or 0

    records = (
        db.query(models.Attendance)
        .filter(models.Attendance.student_id == student_id)
        .order_by(models.Attendance.date.desc())
        .limit(limit)
        .all()
    )

    return {
        "student_id": student_id,
        "total_days": total,
        "days_present": present,
        "attendance_percentage": round(present / total * 100) if total > 0 else 100,
        "records": [
            {"date": str(r.date), "is_present": r.is_present, "remarks": r.remarks or ""}
            for r in records
        ],
    }


@router.get("/summary")
def get_attendance_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    total_rows = (
        db.query(models.Student.grade_level, func.count(models.Attendance.id))
        .join(models.Student, models.Attendance.student_id == models.Student.id)
        .filter(models.Student.is_deleted == False)
        .group_by(models.Student.grade_level)
        .all()
    )
    present_rows = (
        db.query(models.Student.grade_level, func.count(models.Attendance.id))
        .join(models.Student, models.Attendance.student_id == models.Student.id)
        .filter(models.Student.is_deleted == False, models.Attendance.is_present == True)
        .group_by(models.Student.grade_level)
        .all()
    )
    totals   = {g: c for g, c in total_rows}
    presents = {g: c for g, c in present_rows}

    result = []
    for grade in GRADE_ORDER:
        t = totals.get(grade, 0)
        p = presents.get(grade, 0)
        result.append({
            "grade": grade,
            "total_records": t,
            "present": p,
            "percentage": round(p / t * 100) if t > 0 else None,
        })
    return result


@router.get("/today/{grade}")
def get_today_attendance(
    grade: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    today = date.today()

    rows = (
        db.query(models.Student, models.Attendance)
        .outerjoin(
            models.Attendance,
            and_(
                models.Attendance.student_id == models.Student.id,
                models.Attendance.date == today,
            ),
        )
        .filter(
            models.Student.grade_level == grade,
            models.Student.is_deleted == False,
        )
        .all()
    )

    return [
        {
            "student_id": student.id,
            "name": f"{student.first_name} {student.last_name}",
            "is_present": att.is_present if att else True,
            "remarks": att.remarks if att else "",
        }
        for student, att in rows
    ]
