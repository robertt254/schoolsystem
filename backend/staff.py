from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import extract, text
from datetime import date
from pydantic import BaseModel, Field
import secrets, re
from database import get_db
import models, schemas, auth
from audit import log_action
from schemas import PORTAL_ROLES


class PasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8)

router = APIRouter(prefix="/api/staff", tags=["Staff Management"])


def verify_hr_manager(current_user: models.User = Depends(auth.get_current_user)):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admins and the principal can manage staff")
    return current_user


def verify_staff_reader(current_user: models.User = Depends(auth.get_current_user)):
    if current_user.role not in {"admin", "principal", "accountant"}:
        raise HTTPException(status_code=403, detail="Not authorized to view staff list")
    return current_user


def _user_response(user: models.User, days_used: int, include_salary: bool) -> schemas.UserResponse:
    """Single place that shapes a staff record for the API."""
    entitlement = user.accrued_leave_days if user.accrued_leave_days is not None else 21
    return schemas.UserResponse(
        id=user.id,
        username=user.username,
        name=user.name,
        role=user.role,
        job_title=user.job_title,
        contract_type=user.contract_type,
        date_of_hire=user.date_of_hire,
        kra_pin=user.kra_pin,
        nssf_number=user.nssf_number,
        nhif_number=user.nhif_number,
        national_id=user.national_id,
        phone=user.phone,
        email=user.email,
        address=user.address,
        next_of_kin_name=user.next_of_kin_name,
        next_of_kin_phone=user.next_of_kin_phone,
        next_of_kin_relationship=user.next_of_kin_relationship,
        bank_name=user.bank_name if include_salary else None,
        bank_account=user.bank_account if include_salary else None,
        accrued_leave_days=entitlement,
        leave_days_used=days_used,
        leave_days_left=max(0, entitlement - days_used),
        basic_salary=float(user.basic_salary or 0) if include_salary else 0.0,
        allowances=float(user.allowances or 0) if include_salary else 0.0,
        deductions=float(user.deductions or 0) if include_salary else 0.0,
        can_login=user.can_login,
    )


@router.get("/", response_model=list[schemas.UserResponse])
def get_all_staff(db: Session = Depends(get_db), current_user: models.User = Depends(verify_staff_reader)):
    users = db.query(models.User).order_by(models.User.name).all()
    current_year = date.today().year
    # Single query for all staff leave days — avoids N+1 (day counts summed in
    # Python so this works on both PostgreSQL and SQLite)
    leave_rows = db.query(
        models.LeaveRequest.staff_id,
        models.LeaveRequest.start_date,
        models.LeaveRequest.end_date,
    ).filter(
        models.LeaveRequest.status == "approved",
        extract("year", models.LeaveRequest.start_date) == current_year,
    ).all()
    leave_days_by_staff: dict = {}
    for row in leave_rows:
        days = (row.end_date - row.start_date).days + 1
        leave_days_by_staff[row.staff_id] = leave_days_by_staff.get(row.staff_id, 0) + days
    include_salary = current_user.role in {"admin", "accountant"}
    return [
        _user_response(user, leave_days_by_staff.get(user.id, 0), include_salary)
        for user in users
    ]


@router.post("/", response_model=schemas.UserResponse)
def create_staff(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(verify_hr_manager),
):
    # There is exactly ONE system administrator (seeded at first boot) and it
    # stays that way: no user — not even the admin — can create another one.
    if user.role == "admin":
        raise HTTPException(
            status_code=403,
            detail="There is only one system administrator account and another cannot be created",
        )

    is_portal = user.role in PORTAL_ROLES

    if is_portal:
        if not user.password:
            raise HTTPException(status_code=400, detail="Password is required for portal accounts")
        if not user.username:
            raise HTTPException(status_code=400, detail="Username is required for portal accounts")
        if db.query(models.User).filter(models.User.username == user.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        username = user.username
        hashed_pw = auth.get_password_hash(user.password)
    else:
        # Non-portal staff: auto-generate a unique username, set a random unusable password
        slug = re.sub(r'[^a-z0-9]', '', user.name.lower().replace(' ', '_'))[:12] or 'staff'
        base = slug
        suffix = secrets.token_hex(3)
        username = f"{base}_{suffix}"
        while db.query(models.User).filter(models.User.username == username).first():
            username = f"{base}_{secrets.token_hex(3)}"
        hashed_pw = auth.get_password_hash(secrets.token_hex(16))

    new_user = models.User(
        username=username,
        name=user.name,
        role=user.role,
        hashed_password=hashed_pw,
        job_title=user.job_title,
        contract_type=user.contract_type,
        date_of_hire=user.date_of_hire,
        kra_pin=user.kra_pin,
        nssf_number=user.nssf_number,
        nhif_number=user.nhif_number,
        national_id=user.national_id,
        phone=user.phone,
        email=user.email,
        address=user.address,
        next_of_kin_name=user.next_of_kin_name,
        next_of_kin_phone=user.next_of_kin_phone,
        next_of_kin_relationship=user.next_of_kin_relationship,
        bank_name=user.bank_name,
        bank_account=user.bank_account,
        accrued_leave_days=user.accrued_leave_days if user.accrued_leave_days is not None else 21,
        basic_salary=user.basic_salary or 0,
        allowances=user.allowances or 0,
        deductions=user.deductions or 0,
        can_login=is_portal,
    )
    db.add(new_user)
    db.flush()
    log_action(db, admin.id, "CREATE", "staff", new_user.id,
               {"username": user.username, "role": user.role})
    db.commit()
    db.refresh(new_user)
    return _user_response(new_user, 0, admin.role in {"admin", "accountant"})


@router.put("/{user_id}", response_model=schemas.UserResponse)
def update_staff(
    user_id: int,
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(verify_hr_manager),
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Staff member not found")

    if db_user.role == "admin" and admin.role != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can edit another admin account")

    update_data = user_update.model_dump(exclude_unset=True)

    # Single-admin invariant: nobody can be promoted to system administrator,
    # and the one admin account can never lose the role.
    if update_data.get("role") == "admin" and db_user.role != "admin":
        raise HTTPException(status_code=403, detail="No user can be promoted to system administrator")
    if db_user.role == "admin" and update_data.get("role") not in (None, "admin"):
        raise HTTPException(status_code=400, detail="The system administrator's role cannot be changed")
    if "password" in update_data:
        update_data["hashed_password"] = auth.get_password_hash(update_data.pop("password"))

    for key, value in update_data.items():
        setattr(db_user, key, value)

    # Keep can_login in sync with role
    db_user.can_login = db_user.role in PORTAL_ROLES

    log_action(db, admin.id, "UPDATE", "staff", user_id,
               {k: v for k, v in update_data.items() if k != "hashed_password"})
    db.commit()
    db.refresh(db_user)
    current_year = date.today().year
    approved_leaves = (
        db.query(models.LeaveRequest)
        .filter(
            models.LeaveRequest.staff_id == db_user.id,
            models.LeaveRequest.status == "approved",
            extract("year", models.LeaveRequest.start_date) == current_year,
        )
        .all()
    )
    days_used = sum((l.end_date - l.start_date).days + 1 for l in approved_leaves)
    return _user_response(db_user, days_used, admin.role in {"admin", "accountant"})


@router.delete("/{user_id}")
def terminate_staff(
    user_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(verify_hr_manager),
):
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot terminate your own account")

    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Staff member not found")

    # The single system administrator account can never be terminated
    if db_user.role == "admin":
        raise HTTPException(status_code=403, detail="The system administrator account cannot be terminated")

    log_action(db, admin.id, "DELETE", "staff", user_id,
               {"username": db_user.username, "role": db_user.role})
    db.delete(db_user)
    db.commit()
    return {"message": "Staff account terminated"}


@router.post("/{user_id}/reset-password")
def reset_staff_password(
    user_id: int,
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(verify_hr_manager),
):
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Use Change Password to update your own password")

    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Staff member not found")

    # Nobody can reset the system administrator's password — the admin
    # changes it themselves via Change Password.
    if db_user.role == "admin":
        raise HTTPException(
            status_code=403,
            detail="The system administrator's password can only be changed by the administrator themselves",
        )

    db_user.hashed_password = auth.get_password_hash(payload.new_password)
    log_action(db, admin.id, "UPDATE", "staff", user_id,
               {"username": db_user.username, "password_reset": True})
    db.commit()
    return {"message": f"Password for {db_user.name} has been reset successfully"}


@router.get("/audit-logs")
def get_audit_logs(
    action: Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized to view audit logs")

    q = db.query(models.AuditLog)
    if action:
        q = q.filter(models.AuditLog.action == action.upper())
    if resource:
        q = q.filter(models.AuditLog.resource == resource.lower())
    if user_id:
        q = q.filter(models.AuditLog.user_id == user_id)
    if date_from:
        q = q.filter(models.AuditLog.timestamp >= date_from)
    if date_to:
        q = q.filter(models.AuditLog.timestamp <= f"{date_to}T23:59:59")

    logs = q.order_by(models.AuditLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "action": l.action,
            "resource": l.resource,
            "resource_id": l.resource_id,
            "detail": l.detail,
            "timestamp": l.timestamp,
        }
        for l in logs
    ]
