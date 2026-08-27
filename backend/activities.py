"""Transport and co-curricular activity subscriptions and per-activity arrears.

Tuition has its own waterfall in fees.py (oldest term first, priced per grade).
Activities are different: a flat termly fee per activity, owed only by the
students who subscribe (ActivityEnrollment), from the term they joined the
activity onward. This module keeps that arrears math separate rather than
folding it into the tuition waterfall, which would misallocate payments.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models, schemas, auth
from audit import log_action
from notifications import notify_payment
from constants import GENERAL_GRADE, SUBSCRIPTION_CATEGORIES, CAT_TRANSPORT
from fees import _generate_receipt_number, TERM_ORDER, FINANCE_ROLES

router = APIRouter(prefix="/api/activities", tags=["Activities & Transport"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _activity_fee_map(db: Session, year: int) -> dict:
    """activity_name -> (category, unit_price) for a year, in one query."""
    rows = db.query(models.FeeStructure).filter(
        models.FeeStructure.grade_level == GENERAL_GRADE,
        models.FeeStructure.term.in_(SUBSCRIPTION_CATEGORIES),
        models.FeeStructure.academic_year == year,
    ).all()
    return {r.fee_type: (r.term, float(r.amount)) for r in rows}


def _activity_expected(unit_price: float, enrolled_term: str, up_to_term: str) -> float:
    """Terms owed = enrolled_term..up_to_term inclusive. 0 if up_to_term is
    before the student even joined the activity."""
    start = TERM_ORDER.get(enrolled_term, 1)
    end = TERM_ORDER.get(up_to_term, 1)
    if end < start:
        return 0.0
    return round(unit_price * (end - start + 1), 2)


def _student_label(s: models.Student) -> dict:
    return {
        "student_name": f"{s.first_name} {s.last_name}",
        "admission_number": s.admission_number,
        "grade_level": s.grade_level,
    }


def _enrollment_response(e: models.ActivityEnrollment, s: models.Student) -> dict:
    return {
        "id": e.id, "student_id": e.student_id, **_student_label(s),
        "activity_name": e.activity_name, "academic_year": e.academic_year,
        "enrolled_term": e.enrolled_term, "is_active": e.is_active,
        "recorded_by": e.recorded_by, "created_at": e.created_at,
    }


# ── Activity catalogue ───────────────────────────────────────────────────────

@router.get("/", response_model=list[schemas.ActivityInfo])
def list_activities(
    year: Optional[int] = Query(None),
    category: Optional[str] = Query(None, description="Filter to 'Transport' or 'Optional'"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Transport + co-curricular items priced in the fee structure for a year —
    the subscribable catalogue. Configure prices on the Fee Structure page."""
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")
    year = year or datetime.now().year
    fee_map = _activity_fee_map(db, year)
    return [
        {"activity_name": name, "category": cat, "amount": amount}
        for name, (cat, amount) in sorted(fee_map.items())
        if not category or cat == category
    ]


# ── Enrollments (subscriptions) ──────────────────────────────────────────────

@router.get("/enrollments/{student_id}", response_model=list[schemas.ActivityEnrollmentResponse])
def get_student_enrollments(
    student_id: int,
    academic_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")
    student = db.query(models.Student).filter(
        models.Student.id == student_id, models.Student.is_deleted == False,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    q = db.query(models.ActivityEnrollment).filter(models.ActivityEnrollment.student_id == student_id)
    if academic_year:
        q = q.filter(models.ActivityEnrollment.academic_year == academic_year)
    rows = q.order_by(models.ActivityEnrollment.activity_name).all()
    return [_enrollment_response(e, student) for e in rows]


@router.post("/enrollments", status_code=201, response_model=schemas.ActivityEnrollmentResponse)
def create_enrollment(
    payload: schemas.ActivityEnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")
    student = db.query(models.Student).filter(
        models.Student.id == payload.student_id, models.Student.is_deleted == False,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    fee_map = _activity_fee_map(db, payload.academic_year)
    if payload.activity_name not in fee_map:
        raise HTTPException(status_code=400, detail="Activity is not priced in this year's fee structure")

    existing = db.query(models.ActivityEnrollment).filter(
        models.ActivityEnrollment.student_id == payload.student_id,
        models.ActivityEnrollment.activity_name == payload.activity_name,
        models.ActivityEnrollment.academic_year == payload.academic_year,
    ).first()

    if existing and existing.is_active:
        raise HTTPException(status_code=400, detail="Student is already subscribed to this activity")

    if existing:
        # Re-subscribing after a drop — reactivate rather than duplicate.
        existing.is_active = True
        existing.enrolled_term = payload.enrolled_term.value
        existing.recorded_by = current_user.name
        row = existing
        log_action(db, current_user.id, "UPDATE", "activity_enrollment", row.id,
                   {"student_id": payload.student_id, "activity": payload.activity_name, "reactivated": True})
    else:
        row = models.ActivityEnrollment(
            student_id=payload.student_id,
            activity_name=payload.activity_name,
            academic_year=payload.academic_year,
            enrolled_term=payload.enrolled_term.value,
            recorded_by=current_user.name,
        )
        db.add(row)
        db.flush()
        log_action(db, current_user.id, "CREATE", "activity_enrollment", row.id,
                   {"student_id": payload.student_id, "activity": payload.activity_name})

    db.commit()
    db.refresh(row)
    return _enrollment_response(row, student)


@router.delete("/enrollments/{enrollment_id}", status_code=204)
def deactivate_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Unsubscribe a student. Soft delete — flips is_active off so arrears
    already owed for terms they were enrolled remain visible and collectible."""
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")
    row = db.query(models.ActivityEnrollment).filter(models.ActivityEnrollment.id == enrollment_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    row.is_active = False
    log_action(db, current_user.id, "UPDATE", "activity_enrollment", enrollment_id,
               {"unsubscribed": True, "activity": row.activity_name})
    db.commit()


# ── Roster & arrears ─────────────────────────────────────────────────────────

@router.get("/{activity_name}/roster", response_model=schemas.ActivityRosterResponse)
def get_activity_roster(
    activity_name: str,
    term: str = Query(...),
    academic_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Every student subscribed to this activity with expected/paid/arrears up
    to and including the given term, plus a grand total row."""
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")
    if TERM_ORDER.get(term) is None:
        raise HTTPException(status_code=400, detail=f"Invalid term: {term}")
    year = academic_year or datetime.now().year

    fee_map = _activity_fee_map(db, year)
    if activity_name not in fee_map:
        raise HTTPException(status_code=404, detail="Activity not found in the fee structure for this year")
    _category, unit_price = fee_map[activity_name]

    enrollments = (
        db.query(models.ActivityEnrollment, models.Student)
        .join(models.Student, models.ActivityEnrollment.student_id == models.Student.id)
        .filter(
            models.ActivityEnrollment.activity_name == activity_name,
            models.ActivityEnrollment.academic_year == year,
            models.Student.is_deleted == False,
        )
        .all()
    )

    student_ids = [e.student_id for e, _s in enrollments]
    paid_map = {}
    if student_ids:
        paid_rows = db.query(
            models.FeePayment.student_id, func.sum(models.FeePayment.amount).label("total")
        ).filter(
            models.FeePayment.student_id.in_(student_ids),
            models.FeePayment.activity == activity_name,
        ).group_by(models.FeePayment.student_id).all()
        paid_map = {r.student_id: float(r.total) for r in paid_rows}

    entries = []
    total_expected = total_paid = total_outstanding = 0.0
    for e, s in enrollments:
        expected = _activity_expected(unit_price, e.enrolled_term, term)
        paid = paid_map.get(e.student_id, 0.0)
        outstanding = round(max(0.0, expected - paid), 2)
        entries.append({
            "enrollment_id": e.id, "student_id": s.id, **_student_label(s),
            "enrolled_term": e.enrolled_term, "is_active": e.is_active,
            "expected": expected, "paid": round(paid, 2), "outstanding": outstanding,
        })
        total_expected += expected
        total_paid += paid
        total_outstanding += outstanding

    entries.sort(key=lambda r: r["student_name"])
    return {
        "activity_name": activity_name, "term": term, "academic_year": year,
        "unit_price": unit_price, "entries": entries,
        "total_expected": round(total_expected, 2),
        "total_paid": round(total_paid, 2),
        "total_outstanding": round(total_outstanding, 2),
    }


# ── Payments ──────────────────────────────────────────────────────────────────

@router.post("/payments", status_code=201, response_model=schemas.FeeResponse)
def record_activity_payment(
    payload: schemas.ActivityPaymentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Record a payment against one activity subscription. Deliberately does
    NOT go through the tuition waterfall in fees.record_payment — that engine
    allocates against tuition terms and would misfile an activity payment."""
    if current_user.role not in {"accountant", "admin", "secretary", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized to record payments")

    student = db.query(models.Student).filter(
        models.Student.id == payload.student_id, models.Student.is_deleted == False,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    enrollment = db.query(models.ActivityEnrollment).filter(
        models.ActivityEnrollment.student_id == payload.student_id,
        models.ActivityEnrollment.activity_name == payload.activity_name,
        models.ActivityEnrollment.academic_year == payload.academic_year,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=400, detail="Student is not subscribed to this activity")

    fee_map = _activity_fee_map(db, payload.academic_year)
    category = fee_map.get(payload.activity_name, (None, 0.0))[0]
    payment_type = "Transport" if category == CAT_TRANSPORT else "Co-curricular"

    receipt = _generate_receipt_number(db)
    new_fee = models.FeePayment(
        student_id=payload.student_id,
        amount=payload.amount,
        payment_type=payment_type,
        term=payload.term.value,
        activity=payload.activity_name,
        recorded_by=current_user.name,
        receipt_number=receipt,
        **({"payment_date": payload.payment_date} if payload.payment_date else {}),
    )
    db.add(new_fee)
    db.flush()
    log_action(db, current_user.id, "CREATE", "fee", new_fee.id,
               {"receipt": receipt, "amount": str(payload.amount), "student_id": payload.student_id,
                "activity": payload.activity_name})
    db.commit()
    db.refresh(new_fee)

    if student.guardian_phone:
        background_tasks.add_task(
            notify_payment,
            f"{student.first_name} {student.last_name}",
            student.guardian_phone,
            float(payload.amount),
            f"{payload.activity_name} ({payload.term.value})",
            receipt,
        )

    return new_fee
