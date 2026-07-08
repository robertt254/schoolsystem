from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
import models, schemas, auth
from audit import log_action

router = APIRouter(prefix="/api/subjects", tags=["Subjects"])

MANAGE_ROLES = {"admin", "principal"}

# ── CBC curriculum definition ─────────────────────────────────────────────────

CBC_SUBJECTS: dict[str, list[str]] = {
    "Play Group": [
        "Environmental Activities",
        "Language Activities",
        "Psychomotor and Creative Activities",
        "Mathematical Activities",
        "Religious Education Activities",
    ],
    "PP1": [
        "Environmental Activities",
        "Language Activities",
        "Psychomotor and Creative Activities",
        "Mathematical Activities",
        "Religious Education Activities",
    ],
    "PP2": [
        "Environmental Activities",
        "Language Activities",
        "Psychomotor and Creative Activities",
        "Mathematical Activities",
        "Religious Education Activities",
    ],
    "Grade 1": [
        "Mathematical Activities",
        "Literacy",
        "English Language Activities",
        "Hygiene and Nutrition Activities",
        "Religious Education Activities",
        "Environmental Activities",
        "Movement and Creative Activities",
    ],
    "Grade 2": [
        "Mathematical Activities",
        "Literacy",
        "English Language Activities",
        "Hygiene and Nutrition Activities",
        "Religious Education Activities",
        "Environmental Activities",
        "Movement and Creative Activities",
    ],
    "Grade 3": [
        "Mathematical Activities",
        "Literacy",
        "English Language Activities",
        "Hygiene and Nutrition Activities",
        "Religious Education Activities",
        "Environmental Activities",
        "Movement and Creative Activities",
    ],
    "Grade 4": [
        "English",
        "Mathematics",
        "Kiswahili",
        "Science and Technology",
        "Social Studies",
        "Agriculture",
        "Home Science",
        "Creative Arts",
        "Physical and Health Education",
        "Religious Education",
    ],
    "Grade 5": [
        "English",
        "Mathematics",
        "Kiswahili",
        "Science and Technology",
        "Social Studies",
        "Agriculture",
        "Home Science",
        "Creative Arts",
        "Physical and Health Education",
        "Religious Education",
    ],
    "Grade 6": [
        "English",
        "Mathematics",
        "Kiswahili",
        "Science and Technology",
        "Social Studies",
        "Agriculture",
        "Home Science",
        "Creative Arts",
        "Physical and Health Education",
        "Religious Education",
    ],
}

SUBJECT_COLORS: dict[str, str] = {
    "Environmental Activities": "#10B981",
    "Language Activities": "#6366F1",
    "Psychomotor and Creative Activities": "#EC4899",
    "Mathematical Activities": "#F59E0B",
    "Religious Education Activities": "#8B5CF6",
    "Literacy": "#6366F1",
    "English Language Activities": "#3B82F6",
    "Hygiene and Nutrition Activities": "#10B981",
    "Movement and Creative Activities": "#EC4899",
    "English": "#3B82F6",
    "Mathematics": "#F59E0B",
    "Kiswahili": "#F97316",
    "Science and Technology": "#06B6D4",
    "Social Studies": "#6366F1",
    "Agriculture": "#22C55E",
    "Home Science": "#EC4899",
    "Creative Arts": "#A855F7",
    "Physical and Health Education": "#EF4444",
    "Religious Education": "#8B5CF6",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _subject_dict(s: models.Subject, teacher_name: Optional[str]) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "grade_level": s.grade_level,
        "teacher_id": s.teacher_id,
        "teacher_name": teacher_name,
        "color": s.color or SUBJECT_COLORS.get(s.name, "#64748B"),
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _resolve_teacher_name(db: Session, teacher_id: Optional[int]) -> Optional[str]:
    if not teacher_id:
        return None
    u = db.query(models.User.name).filter(models.User.id == teacher_id).first()
    return u.name if u else None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
def list_subjects(
    grade: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = db.query(models.Subject)
    if grade:
        q = q.filter(models.Subject.grade_level == grade)
    rows = q.order_by(models.Subject.grade_level, models.Subject.name).all()
    return [_subject_dict(s, _resolve_teacher_name(db, s.teacher_id)) for s in rows]


@router.get("/by-grade")
def subjects_by_grade(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return {grade: [subjects]} mapping for all grades."""
    rows = db.query(models.Subject).order_by(models.Subject.grade_level, models.Subject.name).all()
    result: dict[str, list] = {}
    for s in rows:
        result.setdefault(s.grade_level, []).append(
            _subject_dict(s, _resolve_teacher_name(db, s.teacher_id))
        )
    return result


@router.post("/", response_model=schemas.SubjectResponse)
def create_subject(
    data: schemas.SubjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in MANAGE_ROLES:
        raise HTTPException(status_code=403, detail="Only admin and principal can manage subjects")

    exists = db.query(models.Subject).filter(
        models.Subject.name == data.name,
        models.Subject.grade_level == data.grade_level,
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Subject already exists for this grade")

    if data.teacher_id:
        teacher = db.query(models.User).filter(models.User.id == data.teacher_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")

    color = data.color or SUBJECT_COLORS.get(data.name, "#64748B")
    new_s = models.Subject(
        name=data.name,
        grade_level=data.grade_level,
        teacher_id=data.teacher_id,
        color=color,
    )
    db.add(new_s)
    db.flush()
    log_action(db, current_user.id, "CREATE", "subject", new_s.id,
               {"name": data.name, "grade_level": data.grade_level})
    db.commit()
    db.refresh(new_s)
    teacher_name = _resolve_teacher_name(db, new_s.teacher_id)
    return schemas.SubjectResponse(
        id=new_s.id, name=new_s.name, grade_level=new_s.grade_level,
        teacher_id=new_s.teacher_id, teacher_name=teacher_name,
        color=new_s.color, created_at=new_s.created_at,
    )


@router.put("/{subject_id}", response_model=schemas.SubjectResponse)
def update_subject(
    subject_id: int,
    data: schemas.SubjectUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in MANAGE_ROLES:
        raise HTTPException(status_code=403, detail="Only admin and principal can manage subjects")

    subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    if data.teacher_id is not None:
        if data.teacher_id == 0:
            subject.teacher_id = None
        else:
            teacher = db.query(models.User).filter(models.User.id == data.teacher_id).first()
            if not teacher:
                raise HTTPException(status_code=404, detail="Teacher not found")
            subject.teacher_id = data.teacher_id

    if data.name is not None:
        subject.name = data.name
    if data.color is not None:
        subject.color = data.color

    log_action(db, current_user.id, "UPDATE", "subject", subject_id,
               data.model_dump(exclude_none=True))
    db.commit()
    db.refresh(subject)
    teacher_name = _resolve_teacher_name(db, subject.teacher_id)
    return schemas.SubjectResponse(
        id=subject.id, name=subject.name, grade_level=subject.grade_level,
        teacher_id=subject.teacher_id, teacher_name=teacher_name,
        color=subject.color, created_at=subject.created_at,
    )


@router.delete("/{subject_id}")
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin"}:
        raise HTTPException(status_code=403, detail="Only admin can delete subjects")

    subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    log_action(db, current_user.id, "DELETE", "subject", subject_id,
               {"name": subject.name, "grade_level": subject.grade_level})
    db.delete(subject)
    db.commit()
    return {"message": "Subject deleted"}


@router.post("/seed")
def seed_cbc_subjects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Populate all grades with the standard CBC subject list. Safe to call multiple times — skips existing entries."""
    if current_user.role not in {"admin"}:
        raise HTTPException(status_code=403, detail="Only admin can seed subjects")

    created = 0
    for grade, subjects in CBC_SUBJECTS.items():
        for name in subjects:
            exists = db.query(models.Subject).filter(
                models.Subject.name == name,
                models.Subject.grade_level == grade,
            ).first()
            if not exists:
                db.add(models.Subject(
                    name=name,
                    grade_level=grade,
                    color=SUBJECT_COLORS.get(name, "#64748B"),
                ))
                created += 1

    db.commit()
    return {"message": f"Seeded {created} new subjects across all grades", "created": created}
