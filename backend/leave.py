from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth
from audit import log_action

router = APIRouter(prefix="/api/leave", tags=["Leave Management"])


@router.post("/", response_model=schemas.LeaveRequestResponse)
def apply_for_leave(
    request: schemas.LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if request.end_date < request.start_date:
        raise HTTPException(status_code=400, detail="End date must be on or after start date")

    new_req = models.LeaveRequest(
        staff_id=current_user.id,
        **request.model_dump(),
        status="pending",
    )
    db.add(new_req)
    db.flush()
    log_action(db, current_user.id, "CREATE", "leave", new_req.id,
               {"leave_type": request.leave_type, "start": str(request.start_date)})
    db.commit()
    db.refresh(new_req)
    return _enrich(new_req, db)


@router.get("/")
def list_leave_requests(
    status: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role in {"admin", "principal"}:
        q = db.query(models.LeaveRequest)
    else:
        q = db.query(models.LeaveRequest).filter(
            models.LeaveRequest.staff_id == current_user.id
        )

    if status:
        if status not in {"pending", "approved", "rejected"}:
            raise HTTPException(status_code=400, detail="status must be pending, approved, or rejected")
        q = q.filter(models.LeaveRequest.status == status)

    rows = q.order_by(models.LeaveRequest.created_at.desc()).all()
    return [_enrich(r, db) for r in rows]


@router.put("/{request_id}/review")
def review_leave_request(
    request_id: int,
    action: str,  # "approve" | "reject"
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admins and the principal can review leave requests")

    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    row = db.query(models.LeaveRequest).filter(models.LeaveRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Leave request has already been reviewed")

    row.status = "approved" if action == "approve" else "rejected"
    row.reviewed_by = current_user.id
    row.reviewed_at = datetime.now(timezone.utc)

    log_action(db, current_user.id, "UPDATE", "leave", request_id, {"status": row.status})
    db.commit()
    db.refresh(row)
    return _enrich(row, db)


@router.delete("/{request_id}")
def cancel_leave_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    row = db.query(models.LeaveRequest).filter(models.LeaveRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if row.staff_id != current_user.id and current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this request")

    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be cancelled")

    log_action(db, current_user.id, "DELETE", "leave", request_id)
    db.delete(row)
    db.commit()
    return {"message": "Leave request cancelled"}


def _enrich(row: models.LeaveRequest, db: Session) -> dict:
    staff = db.query(models.User).filter(models.User.id == row.staff_id).first()
    return {
        "id": row.id,
        "staff_id": row.staff_id,
        "staff_name": staff.name if staff else "Unknown",
        "leave_type": row.leave_type,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "reason": row.reason,
        "status": row.status,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at,
        "created_at": row.created_at,
    }
