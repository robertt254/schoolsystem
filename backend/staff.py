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
    result = []
    for user in users:
        days_used = leave_days_by_staff.get(user.id, 0)
        entitlement = user.accrued_leave_days if user.accrued_leave_days is not None else 21
        result.append(schemas.UserResponse(
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
            accrued_leave_days=entitlement,
            leave_days_used=days_used,
            leave_days_left=max(0, entitlement - days_used),
            basic_salary=float(user.basic_salary or 0) if include_salary else 0.0,
            allowances=float(user.allowances or 0) if include_salary else 0.0,
            deductions=float(user.deductions or 0) if include_salary else 0.0,
            can_login=user.can_login,
        ))
    return result


@router.post("/", response_model=schemas.UserResponse)
def create_staff(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(verify_hr_manager),
):
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
    entitlement = new_user.accrued_leave_days if new_user.accrued_leave_days is not None else 21
    include_salary = admin.role in {"admin", "accountant"}
    return schemas.UserResponse(
        id=new_user.id,
        username=new_user.username,
        name=new_user.name,
        role=new_user.role,
        job_title=new_user.job_title,
        contract_type=new_user.contract_type,
        date_of_hire=new_user.date_of_hire,
        kra_pin=new_user.kra_pin,
        nssf_number=new_user.nssf_number,
        nhif_number=new_user.nhif_number,
        accrued_leave_days=entitlement,
        leave_days_used=0,
        leave_days_left=entitlement,
        basic_salary=float(new_user.basic_salary or 0) if include_salary else 0.0,
        allowances=float(new_user.allowances or 0) if include_salary else 0.0,
        deductions=float(new_user.deductions or 0) if include_salary else 0.0,
        can_login=new_user.can_login,
    )


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
    entitlement = db_user.accrued_leave_days if db_user.accrued_leave_days is not None else 21
    include_salary = admin.role in {"admin", "accountant"}
    return schemas.UserResponse(
        id=db_user.id,
        username=db_user.username,
        name=db_user.name,
        role=db_user.role,
        job_title=db_user.job_title,
        contract_type=db_user.contract_type,
        date_of_hire=db_user.date_of_hire,
        kra_pin=db_user.kra_pin,
        nssf_number=db_user.nssf_number,
        nhif_number=db_user.nhif_number,
        accrued_leave_days=entitlement,
        leave_days_used=days_used,
        leave_days_left=max(0, entitlement - days_used),
        basic_salary=float(db_user.basic_salary or 0) if include_salary else 0.0,
        allowances=float(db_user.allowances or 0) if include_salary else 0.0,
        deductions=float(db_user.deductions or 0) if include_salary else 0.0,
        can_login=db_user.can_login,
    )


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

    # Only admins can terminate other admin accounts
    if db_user.role == "admin" and admin.role != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can terminate another admin account")

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

    if db_user.role == "admin" and admin.role != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can reset another admin's password")

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
