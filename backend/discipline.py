from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth
from audit import log_action
from typing import Optional

router = APIRouter(prefix="/api/discipline", tags=["Discipline"])

WRITE_ROLES = {"admin", "principal", "teacher", "senior_teacher", "secretary"}


def _serialize(r: models.DisciplinaryRecord, db: Session) -> dict:
    student = db.query(models.Student).filter(models.Student.id == r.student_id).first()
    return {
        "id": r.id,
        "student_id": r.student_id,
        "student_name": f"{student.first_name} {student.last_name}" if student else "Unknown",
        "grade_level": student.grade_level if student else "",
        "incident_date": r.incident_date,
        "incident_type": r.incident_type,
        "description": r.description,
        "action_taken": r.action_taken,
        "action_date": r.action_date,
        "severity": r.severity,
        "status": r.status,
        "recorded_by": r.recorded_by,
        "created_at": r.created_at,
    }


@router.get("/")
def list_records(
    student_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    grade_level: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = db.query(models.DisciplinaryRecord)
    if student_id:
        q = q.filter(models.DisciplinaryRecord.student_id == student_id)
    if status:
        q = q.filter(models.DisciplinaryRecord.status == status)
    if grade_level:
        student_ids = [
            s.id for s in db.query(models.Student).filter(
                models.Student.grade_level == grade_level,
                models.Student.is_deleted == False,
            ).all()
        ]
        q = q.filter(models.DisciplinaryRecord.student_id.in_(student_ids))

    records = q.order_by(models.DisciplinaryRecord.incident_date.desc()).all()
    return [_serialize(r, db) for r in records]


@router.post("/", status_code=201)
def create_record(
    payload: schemas.DisciplineCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")

    student = db.query(models.Student).filter(
        models.Student.id == payload.student_id,
        models.Student.is_deleted == False,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    record = models.DisciplinaryRecord(
        student_id=payload.student_id,
        incident_date=payload.incident_date,
        incident_type=payload.incident_type,
        description=payload.description,
        action_taken=payload.action_taken,
        action_date=payload.action_date,
        severity=payload.severity,
        status="Open",
        recorded_by=current_user.name,
    )
    db.add(record)
    db.flush()
    log_action(db, current_user.id, "CREATE", "discipline", record.id,
               {"student_id": payload.student_id, "type": payload.incident_type})
    db.commit()
    db.refresh(record)
    return _serialize(record, db)


@router.put("/{record_id}")
def update_record(
    record_id: int,
    payload: schemas.DisciplineUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")

    record = db.query(models.DisciplinaryRecord).filter(
        models.DisciplinaryRecord.id == record_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(record, field, value)

    log_action(db, current_user.id, "UPDATE", "discipline", record_id)
    db.commit()
    db.refresh(record)
    return _serialize(record, db)


@router.delete("/{record_id}", status_code=204)
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized")

    record = db.query(models.DisciplinaryRecord).filter(
        models.DisciplinaryRecord.id == record_id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    log_action(db, current_user.id, "DELETE", "discipline", record_id)
    db.delete(record)
    db.commit()
