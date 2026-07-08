from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from database import get_db
import models, auth
from notifications import send_bulk_sms
from audit import log_action

router = APIRouter(prefix="/api/sms", tags=["SMS"])

COMMS_ROLES = {"secretary", "principal", "admin"}


class BroadcastRequest(BaseModel):
    message: str = Field(..., min_length=5, max_length=500)
    grade: Optional[str] = None  # None = all parents


def _do_broadcast(phones: list, message: str) -> None:
    send_bulk_sms(phones, message)


@router.post("/broadcast")
def broadcast_sms(
    payload: BroadcastRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in COMMS_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to send broadcast SMS")

    query = db.query(models.Student.guardian_phone, models.Student.grade_level).filter(
        models.Student.is_deleted == False,
        models.Student.guardian_phone.isnot(None),
        models.Student.guardian_phone != "",
    )
    if payload.grade:
        query = query.filter(models.Student.grade_level == payload.grade)

    rows = query.all()
    phones = list({row.guardian_phone for row in rows})  # deduplicate

    if not phones:
        raise HTTPException(status_code=400, detail="No guardian phone numbers found for the selected filter")

    background_tasks.add_task(_do_broadcast, phones, payload.message)

    log_action(db, current_user.id, "CREATE", "sms_broadcast", None, {
        "grade": payload.grade or "all",
        "recipient_count": len(phones),
        "message_preview": payload.message[:80],
    })
    db.commit()

    return {"message": f"Broadcasting to {len(phones)} guardian(s) in background", "recipient_count": len(phones)}


@router.get("/preview")
def preview_recipients(
    grade: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return the count of reachable guardians for a given grade filter."""
    if current_user.role not in COMMS_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")

    query = db.query(models.Student).filter(
        models.Student.is_deleted == False,
        models.Student.guardian_phone.isnot(None),
        models.Student.guardian_phone != "",
    )
    if grade:
        query = query.filter(models.Student.grade_level == grade)

    students = query.all()
    phones = list({s.guardian_phone for s in students})
    return {"recipient_count": len(phones), "grade": grade or "all"}
