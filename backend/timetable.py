from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth
from audit import log_action

router = APIRouter(prefix="/api/timetable", tags=["Timetable"])

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


@router.get("/{grade}/{term}")
def get_timetable(
    grade: str,
    term: str,
    year: int = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    from datetime import datetime
    if year is None:
        year = datetime.now().year

    entries = (
        db.query(models.Timetable)
        .filter(
            models.Timetable.grade_level == grade,
            models.Timetable.term == term,
            models.Timetable.academic_year == year,
        )
        .order_by(models.Timetable.day_of_week, models.Timetable.period)
        .all()
    )

    grid = {day: {} for day in DAYS}
    for e in entries:
        grid[e.day_of_week][e.period] = {
            "id": e.id,
            "subject": e.subject,
            "teacher_name": e.teacher_name,
            "start_time": e.start_time,
            "end_time": e.end_time,
        }
    return {"grade_level": grade, "term": term, "academic_year": year, "grid": grid}


@router.post("/")
def upsert_timetable_entry(
    entry: schemas.TimetableCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal", "teacher"}:
        raise HTTPException(status_code=403, detail="Not authorized to manage timetables")

    existing = db.query(models.Timetable).filter(
        models.Timetable.grade_level == entry.grade_level,
        models.Timetable.day_of_week == entry.day_of_week,
        models.Timetable.period == entry.period,
        models.Timetable.term == entry.term,
        models.Timetable.academic_year == entry.academic_year,
    ).first()

    if existing:
        for key, value in entry.model_dump().items():
            setattr(existing, key, value)
        log_action(db, current_user.id, "UPDATE", "timetable", existing.id, entry.model_dump())
        db.commit()
        db.refresh(existing)
        return existing
    else:
        new_entry = models.Timetable(**entry.model_dump(), created_by=current_user.name)
        db.add(new_entry)
        db.flush()
        log_action(db, current_user.id, "CREATE", "timetable", new_entry.id, entry.model_dump())
        db.commit()
        db.refresh(new_entry)
        return new_entry


@router.delete("/{entry_id}")
def delete_timetable_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized")

    row = db.query(models.Timetable).filter(models.Timetable.id == entry_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Timetable entry not found")

    log_action(db, current_user.id, "DELETE", "timetable", entry_id)
    db.delete(row)
    db.commit()
    return {"message": "Timetable entry deleted"}
