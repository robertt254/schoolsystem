import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import date
from database import get_db
import models, auth
from fees import compute_effective_term_collection, _get_expected_fee, _get_rollover_credit, TERM_ORDER

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

GRADE_ORDER = [
    "Play Group", "PP1", "PP2",
    "Grade 1", "Grade 2", "Grade 3",
    "Grade 4", "Grade 5", "Grade 6",
]


@router.get("/stats")
def get_dashboard_stats(
    term: str = Query(default="Term 1"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    total_students = db.query(func.count(models.Student.id)).filter(
        models.Student.is_deleted == False
    ).scalar() or 0

    total_staff = db.query(func.count(models.User.id)).scalar() or 0

    # Net revenue = total fees collected minus payroll and expenses disbursed
    total_fees     = float(db.query(func.sum(models.FeePayment.amount)).scalar() or 0)
    total_payroll  = float(db.query(func.sum(models.Payroll.net_pay)).scalar() or 0)
    total_expenses = float(db.query(func.sum(models.Expense.amount)).scalar() or 0)
    net_revenue    = round(total_fees - total_payroll - total_expenses, 2)

    # Today's attendance rate
    today = date.today()
    today_records = db.query(func.count(models.Attendance.id)).filter(
        cast(models.Attendance.date, Date) == today
    ).scalar() or 0
    today_present = db.query(func.count(models.Attendance.id)).filter(
        cast(models.Attendance.date, Date) == today,
        models.Attendance.is_present == True,
    ).scalar() or 0
    today_attendance_pct = (
        round(today_present / today_records * 100) if today_records > 0 else None
    )

    # Term fee collection (effective: overpayments capped per student, not inflating %)
    try:
        active_students = db.query(models.Student).filter(
            models.Student.is_deleted == False,
            models.Student.status == "Active",
        ).all()
        term_expected = round(sum(_get_expected_fee(db, s.grade_level, term) for s in active_students), 2)
        term_collected = compute_effective_term_collection(db, active_students, term)
        term_pct = round(term_collected / term_expected * 100) if term_expected > 0 else 0

        # Defaulters count — students whose effective paid < expected (reuses rollover logic)
        term_num = TERM_ORDER.get(term, 1)
        defaulters_count = 0
        for s in active_students:
            expected_s = _get_expected_fee(db, s.grade_level, term)
            direct_paid = float(
                db.query(func.sum(models.FeePayment.amount))
                .filter(models.FeePayment.student_id == s.id, models.FeePayment.term == term)
                .scalar() or 0
            )
            rollover = _get_rollover_credit(db, s.id, s.grade_level, term_num)
            if (direct_paid + rollover) < expected_s:
                defaulters_count += 1
    except Exception:
        db.rollback()  # reset aborted transaction so subsequent queries work
        active_students = []
        term_expected = 0
        term_collected = 0
        term_pct = 0
        defaulters_count = 0

    # Recent activity feed with richer detail
    recent_logs = (
        db.query(models.AuditLog, models.User)
        .outerjoin(models.User, models.AuditLog.user_id == models.User.id)
        .order_by(models.AuditLog.timestamp.desc())
        .limit(12)
        .all()
    )

    activity = []
    for log, user in recent_logs:
        detail = {}
        if log.detail:
            try:
                detail = json.loads(log.detail)
            except Exception:
                pass
        # Build a human-readable description
        if log.resource == "student":
            name = f"{detail.get('first_name', '')} {detail.get('last_name', '')}".strip()
            desc = f"admitted {name}" if log.action == "CREATE" and name else \
                   f"updated student record" if log.action == "UPDATE" else \
                   f"removed a student record"
        elif log.resource == "fee":
            amount = detail.get("amount")
            if log.action == "DELETE":
                desc = f"deleted a KES {int(float(amount)):,} fee record" if amount else "deleted a fee record"
            else:
                desc = f"recorded KES {int(float(amount)):,} payment" if amount else "recorded a fee payment"
        elif log.resource == "staff":
            name = detail.get("username", "")
            desc = f"hired staff @{name}" if log.action == "CREATE" and name else \
                   f"updated staff record" if log.action == "UPDATE" else \
                   f"terminated staff @{name}"
        elif log.resource == "assessment":
            desc = "entered CBC assessment scores"
        elif log.resource == "attendance":
            desc = "marked attendance"
        elif log.resource == "payroll":
            desc = "executed payroll"
        elif log.resource == "expense":
            desc = "recorded an expense"
        else:
            desc = f"{log.action.lower()}d a {log.resource} record"

        activity.append({
            "id": log.id,
            "action": log.action,
            "resource": log.resource,
            "description": desc,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "user_name": user.name if user else "System",
        })

    return {
        "total_students": total_students,
        "total_staff": total_staff,
        "total_revenue": net_revenue,
        "today_attendance_pct": today_attendance_pct,
        "today_records": today_records,
        "term_collected": term_collected,
        "term_expected": term_expected,
        "term_pct": min(term_pct, 100),
        "defaulters_count": defaulters_count,
        "recent_activity": activity,
    }


@router.get("/grade-stats")
def get_grade_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    rows = (
        db.query(models.Student.grade_level, func.count(models.Student.id))
        .filter(models.Student.is_deleted == False, models.Student.status == "Active")
        .group_by(models.Student.grade_level)
        .all()
    )
    counts = {g: c for g, c in rows}
    return [{"grade": g, "count": counts.get(g, 0)} for g in GRADE_ORDER]
