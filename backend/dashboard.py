import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import date, timedelta
from database import get_db
import models, auth
from fees import _expected_fee_map, _expected_from_map_for_student, _paid_map, TERM_ORDER, TERM_BY_NUM

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

# Net revenue reveals what the school makes — restricted to the roles who
# also see it on the Finance Dashboard's term-accountability table (see
# auth.js `canFinance` on the frontend, mirrored here server-side).
REVENUE_VISIBLE_ROLES = {"admin", "principal", "accountant"}

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

    # Net revenue = total fees collected minus payroll and expenses disbursed.
    # What the school makes is restricted to admin/principal/accountant —
    # omitted entirely for other roles rather than sent as 0 (which could be
    # misread as "no revenue").
    net_revenue = None
    if current_user.role in REVENUE_VISIBLE_ROLES:
        total_fees     = float(db.query(func.sum(models.FeePayment.amount)).filter(
            models.FeePayment.is_voided == False).scalar() or 0)
        total_payroll  = float(db.query(func.sum(models.Payroll.net_pay)).scalar() or 0)
        total_expenses = float(db.query(func.sum(models.Expense.amount)).scalar() or 0)
        net_revenue    = round(total_fees - total_payroll - total_expenses, 2)

    # Upcoming events (next 7 days) — shown in place of Net Revenue for roles
    # that can't see school financials.
    today = date.today()
    upcoming_events = db.query(func.count(models.SchoolEvent.id)).filter(
        models.SchoolEvent.start_date >= today,
        models.SchoolEvent.start_date <= today + timedelta(days=7),
    ).scalar() or 0

    # Today's attendance rate
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

    # Term fee collection (effective: overpayments capped per student, not
    # inflating %) and defaulter count — one pass over three batched queries.
    try:
        active_students = db.query(models.Student).filter(
            models.Student.is_deleted == False,
            models.Student.status == "Active",
        ).all()
        fee_map = _expected_fee_map(db)
        paid_map = _paid_map(db, [s.id for s in active_students])
        term_num = TERM_ORDER.get(term, 1)
        prior_terms = [TERM_BY_NUM[n] for n in range(1, term_num)]

        term_expected = 0.0
        term_collected = 0.0
        defaulters_count = 0
        for s in active_students:
            expected_s = _expected_from_map_for_student(fee_map, s, term)
            term_expected += expected_s
            direct_paid = paid_map.get((s.id, term), 0.0)
            cum_expected = sum(_expected_from_map_for_student(fee_map, s, t) for t in prior_terms)
            cum_paid = sum(paid_map.get((s.id, t), 0.0) for t in prior_terms)
            rollover = max(0.0, round(cum_paid - cum_expected, 2))
            if expected_s > 0:
                term_collected += min(direct_paid + rollover, expected_s)
            if (direct_paid + rollover) < expected_s:
                defaulters_count += 1
        term_expected = round(term_expected, 2)
        term_collected = round(term_collected, 2)
        term_pct = round(term_collected / term_expected * 100) if term_expected > 0 else 0
    except Exception:
        db.rollback()  # reset aborted transaction so subsequent queries work
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
        # Build a human-readable description. Branch on the action FIRST, not
        # on whether a name happens to be present — a chained "A if cond1
        # else B if cond2 else C" falls through to C (e.g. "removed") for a
        # CREATE whose logged detail is missing a name, misreporting the
        # action entirely rather than just omitting the name.
        if log.resource == "student":
            name = f"{detail.get('first_name', '')} {detail.get('last_name', '')}".strip()
            if log.action == "CREATE":
                desc = f"admitted {name}" if name else "admitted a new student"
            elif log.action == "UPDATE":
                desc = "updated student record"
            else:
                desc = "removed a student record"
        elif log.resource == "fee":
            amount = detail.get("amount")
            if log.action == "DELETE":
                desc = f"deleted a KES {int(float(amount)):,} fee record" if amount else "deleted a fee record"
            else:
                desc = f"recorded KES {int(float(amount)):,} payment" if amount else "recorded a fee payment"
        elif log.resource == "staff":
            name = detail.get("username", "")
            if log.action == "CREATE":
                desc = f"hired staff @{name}" if name else "hired a new staff member"
            elif log.action == "UPDATE":
                desc = "updated staff record"
            else:
                desc = f"terminated staff @{name}" if name else "terminated a staff member"
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
        "upcoming_events": upcoming_events,
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
