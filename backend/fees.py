import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from database import get_db
import models, schemas, auth
from audit import log_action
from notifications import notify_payment
from constants import CBC_TERMLY_FEES, TERM_ORDER, TERM_BY_NUM, fee_structure_template_rows

router = APIRouter(prefix="/api/fees", tags=["Finance & Fees"])

# Keep local alias so internal helpers are unchanged
CBC_TERMLY_FEES_FALLBACK = CBC_TERMLY_FEES

FINANCE_ROLES = {"accountant", "admin", "principal", "secretary"}


# ── Helpers ───────────────────────────────────────────────────────────────────

ALL_TERMS = ["Term 1", "Term 2", "Term 3"]


def _generate_receipt_number(db: Session) -> str:
    """Atomic receipt number using a PostgreSQL sequence — no race condition possible.
    Falls back to a max-id scan on databases without sequences (e.g. SQLite in dev)."""
    year = datetime.now().year
    if db.get_bind().dialect.name == "postgresql":
        seq = db.execute(text("SELECT nextval('receipt_number_seq')")).scalar()
    else:
        from sqlalchemy import func as _func
        seq = (db.query(_func.max(models.FeePayment.id)).scalar() or 0) + 1
    return f"BNS-{year}-{seq:05d}"


def _term_index(term: str) -> int:
    """Return 0-based position of a term string, -1 if unknown."""
    try:
        return ALL_TERMS.index(term)
    except ValueError:
        return -1


def _get_expected_fee(db: Session, grade_level: str, term: str) -> float:
    year = datetime.now().year
    structure = (
        db.query(models.FeeStructure)
        .filter(
            models.FeeStructure.grade_level == grade_level,
            models.FeeStructure.term == term,
            models.FeeStructure.academic_year == year,
            models.FeeStructure.fee_type == "Tuition",
        )
        .first()
    )
    if structure:
        return float(structure.amount)
    return CBC_TERMLY_FEES_FALLBACK.get(grade_level, 0.0)


def _owes_term(student, term: str) -> bool:
    """Mid-year joiners owe nothing for terms before their admission term.
    Students without an admission year (enrolled before this year, or legacy
    records) owe every term — the pre-existing behaviour."""
    year = datetime.now().year
    admission_year = getattr(student, "admission_year", None)
    if admission_year is None or admission_year < year:
        return True
    if admission_year > year:
        return False
    admission_term = getattr(student, "admission_term", None) or "Term 1"
    return TERM_ORDER.get(term, 1) >= TERM_ORDER.get(admission_term, 1)


def _expected_fee_for_student(db: Session, student, term: str) -> float:
    if not _owes_term(student, term):
        return 0.0
    return _get_expected_fee(db, student.grade_level, term)


def _get_rollover_credit(db: Session, student, up_to_term_num: int) -> float:
    """Return the cumulative overpayment from all terms before up_to_term_num (within same year)."""
    cumulative_expected = 0.0
    cumulative_paid = 0.0
    for num in range(1, up_to_term_num):
        t = TERM_BY_NUM[num]
        cumulative_expected += _expected_fee_for_student(db, student, t)
        paid = db.query(func.sum(models.FeePayment.amount)).filter(
            models.FeePayment.student_id == student.id,
            models.FeePayment.term == t,
            models.FeePayment.activity.is_(None),
            models.FeePayment.is_voided == False,
        ).scalar() or 0.0
        cumulative_paid += float(paid)
    return max(0.0, round(cumulative_paid - cumulative_expected, 2))


def _get_carry_forward(db: Session, student_id: int, academic_year: str, term: str) -> float:
    """Sum of all explicit carry-forward adjustments for this student/year/term."""
    total = db.query(func.sum(models.FeeCarryForward.amount)).filter(
        models.FeeCarryForward.student_id == student_id,
        models.FeeCarryForward.academic_year == academic_year,
        models.FeeCarryForward.term == term,
    ).scalar()
    return float(total or 0.0)


def _term_outstanding(db: Session, student, term: str, year_str: str) -> float:
    """Outstanding balance for one term, using the same definition as the
    student-balance endpoint (expected + carry-forward − paid − prior rollover).
    Terms before a mid-year joiner's admission term expect nothing.

    `activity.is_(None)` on every "paid" query below/elsewhere in this file
    excludes Transport/Co-curricular/Other payments (they set FeePayment.
    activity) from tuition's paid sum — otherwise a parent paying for
    Swimming would appear to have paid down tuition arrears too.
    `is_voided == False` excludes voided (corrected-mistake) payments —
    see void_payment."""
    expected = _expected_fee_for_student(db, student, term)
    total_paid = float(
        db.query(func.sum(models.FeePayment.amount))
        .filter(
            models.FeePayment.student_id == student.id,
            models.FeePayment.term == term,
            models.FeePayment.activity.is_(None),
            models.FeePayment.is_voided == False,
        )
        .scalar() or 0.0
    )
    term_num = TERM_ORDER.get(term, 1)
    rollover = _get_rollover_credit(db, student, term_num)
    carry = _get_carry_forward(db, student.id, year_str, term)
    return round(max(0.0, expected + carry - total_paid - rollover), 2)


def _compute_allocation(db: Session, student, amount: float, current_term: str):
    """
    Waterfall allocation: apply `amount` to outstanding balances OLDEST term
    first, up to and including the current term. Any remainder beyond all
    current obligations is recorded as a prepayment on the current term.

    Returns (allocation, total_outstanding_before, advance):
      allocation  — list of {term, amount, kind} where kind is 'arrears' for a
                    prior term or 'current' for the current term.
      total_outstanding_before — sum of balances across terms ≤ current (pre-payment).
      advance     — amount left after clearing every term ≤ current (true prepayment).
    """
    cur_num = TERM_ORDER.get(current_term, 1)
    year_str = str(datetime.now().year)
    remaining = round(float(amount), 2)

    outstanding = {}
    total_outstanding_before = 0.0
    for tnum in range(1, cur_num + 1):
        t = TERM_BY_NUM[tnum]
        bal = _term_outstanding(db, student, t, year_str)
        outstanding[t] = bal
        total_outstanding_before += bal

    allocation = []
    for tnum in range(1, cur_num + 1):
        if remaining <= 0:
            break
        t = TERM_BY_NUM[tnum]
        bal = outstanding[t]
        if bal <= 0:
            continue
        portion = round(min(remaining, bal), 2)
        allocation.append({
            "term": t,
            "amount": portion,
            "kind": "arrears" if tnum < cur_num else "current",
        })
        remaining = round(remaining - portion, 2)

    # Any remainder is a prepayment on the current term — kept as its own line so
    # the allocation parts always sum exactly to the payment amount.
    advance = round(remaining, 2)
    if remaining > 0:
        allocation.append({"term": current_term, "amount": remaining, "kind": "advance"})

    # Guard: a positive payment always produces at least one allocation row.
    if not allocation:
        allocation.append({"term": current_term, "amount": round(float(amount), 2), "kind": "advance"})

    return allocation, round(total_outstanding_before, 2), advance


def _expected_fee_map(db: Session) -> dict:
    """(grade_level, term) → configured tuition for the current year, in one query."""
    year = datetime.now().year
    rows = db.query(models.FeeStructure).filter(
        models.FeeStructure.academic_year == year,
        models.FeeStructure.fee_type == "Tuition",
    ).all()
    return {(r.grade_level, r.term): float(r.amount) for r in rows}


def _expected_from_map(fee_map: dict, grade_level: str, term: str) -> float:
    return fee_map.get((grade_level, term), CBC_TERMLY_FEES_FALLBACK.get(grade_level, 0.0))


def _expected_from_map_for_student(fee_map: dict, student, term: str) -> float:
    """Batched variant of _expected_fee_for_student."""
    if not _owes_term(student, term):
        return 0.0
    return _expected_from_map(fee_map, student.grade_level, term)


def _paid_map(db: Session, student_ids: list) -> dict:
    """(student_id, term) → summed TUITION payments, in one grouped query.
    Excludes Transport/Co-curricular/Other payments (activity IS NOT NULL)
    and voided payments — see _term_outstanding."""
    if not student_ids:
        return {}
    rows = db.query(
        models.FeePayment.student_id,
        models.FeePayment.term,
        func.sum(models.FeePayment.amount).label("total"),
    ).filter(
        models.FeePayment.student_id.in_(student_ids),
        models.FeePayment.activity.is_(None),
        models.FeePayment.is_voided == False,
    ).group_by(
        models.FeePayment.student_id, models.FeePayment.term
    ).all()
    return {(r.student_id, r.term): float(r.total) for r in rows}


def compute_effective_term_collection(db: Session, students: list, term: str) -> float:
    """
    Compute the portion of payments that count toward `term`.

    Each student's contribution is capped at their expected fee for the term.
    Overpayments from prior terms are brought in as rollover credit before capping.
    This prevents overpayments in Term 1 from inflating Term 1's completion %.

    Batched: three queries total regardless of the number of students.
    """
    if not students:
        return 0.0
    term_num = TERM_ORDER.get(term, 1)
    fee_map = _expected_fee_map(db)
    paid = _paid_map(db, [s.id for s in students])
    prior_terms = [TERM_BY_NUM[n] for n in range(1, term_num)]

    total = 0.0
    for s in students:
        expected = _expected_from_map_for_student(fee_map, s, term)
        if expected <= 0:
            continue
        direct_paid = paid.get((s.id, term), 0.0)
        cum_expected = sum(_expected_from_map_for_student(fee_map, s, t) for t in prior_terms)
        cum_paid = sum(paid.get((s.id, t), 0.0) for t in prior_terms)
        rollover = max(0.0, round(cum_paid - cum_expected, 2))
        total += min(direct_paid + rollover, expected)
    return round(total, 2)


# ── Payment endpoints ─────────────────────────────────────────────────────────

@router.get("/smart-term/{student_id}")
def get_smart_term(
    student_id: int,
    current_term: str = Query(..., description="The school's current active term"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Returns the recommended payment term for a student.
    Scans from Term 1 up to (and including) current_term for outstanding balances.
    The first term with a positive outstanding becomes the recommended term.
    Allowed terms are all terms ≤ current_term.
    """
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")

    cur_idx = _term_index(current_term)
    if cur_idx < 0:
        raise HTTPException(status_code=400, detail=f"Invalid current_term: {current_term}")

    allowed_terms = ALL_TERMS[: cur_idx + 1]

    recommended_term = current_term
    outstanding_balance = 0.0

    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    for term in allowed_terms:
        paid = float(
            db.query(func.sum(models.FeePayment.amount))
            .filter(models.FeePayment.student_id == student_id, models.FeePayment.term == term,
                    models.FeePayment.activity.is_(None), models.FeePayment.is_voided == False)
            .scalar() or 0
        )
        # Mid-year joiners expect nothing before their admission term
        expected = _expected_fee_for_student(db, student, term)
        balance = round(expected - paid, 2)
        if balance > 0:
            recommended_term = term
            outstanding_balance = balance
            break

    return {
        "recommended_term": recommended_term,
        "outstanding_balance": outstanding_balance,
        "allowed_terms": allowed_terms,
        "current_term": current_term,
    }


@router.get("/allocation-preview", response_model=schemas.AllocationPreview)
def allocation_preview(
    student_id: int,
    amount: float = Query(..., gt=0),
    current_term: str = Query(..., description="The school's current active term"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Preview how a payment would be split across terms, without recording it."""
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")
    if _term_index(current_term) < 0:
        raise HTTPException(status_code=400, detail=f"Invalid current_term: {current_term}")

    student = db.query(models.Student).filter(
        models.Student.id == student_id,
        models.Student.is_deleted == False,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    allocation, total_before, advance = _compute_allocation(db, student, amount, current_term)
    return {
        "student_id": student.id,
        "student_name": f"{student.first_name} {student.last_name}",
        "grade_level": student.grade_level,
        "current_term": current_term,
        "amount": round(float(amount), 2),
        "allocation": allocation,
        "total_outstanding_before": total_before,
        "remaining_after": advance,
    }


@router.post("/", response_model=schemas.FeeResponse)
def record_payment(
    fee: schemas.FeeCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"accountant", "admin", "secretary", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized to record payments")

    # The school's active term drives the waterfall. Fall back to the payment's
    # term for backwards-compatible callers that don't send current_term.
    current_term = (fee.current_term or fee.term)
    if _term_index(current_term) < 0:
        raise HTTPException(status_code=400, detail=f"Invalid current_term: {current_term}")

    student = (
        db.query(models.Student)
        .filter(
            models.Student.id == fee.student_id,
            models.Student.is_deleted == False,
        )
        .with_for_update()
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Waterfall: clear oldest arrears first, carry remainder to the current term.
    allocation, _total_before, _advance = _compute_allocation(
        db, student, float(fee.amount), current_term
    )
    # Tag the row to the earliest term the payment touches so existing balance /
    # rollover logic stays correct; the JSON allocation carries the full split.
    primary_term = allocation[0]["term"]

    data = fee.model_dump(exclude={"current_term"})
    data["term"] = primary_term
    # Backdated only when explicitly provided; otherwise the DB stamps "now"
    if not data.get("payment_date"):
        data.pop("payment_date", None)
    receipt = _generate_receipt_number(db)
    new_fee = models.FeePayment(
        **data,
        recorded_by=current_user.name,
        receipt_number=receipt,
        allocation=json.dumps(allocation),
    )
    db.add(new_fee)
    db.flush()
    log_action(db, current_user.id, "CREATE", "fee", new_fee.id,
               {"receipt": receipt, "amount": str(fee.amount), "student_id": fee.student_id,
                "allocation": allocation})
    db.commit()
    db.refresh(new_fee)

    if student.guardian_phone:
        background_tasks.add_task(
            notify_payment,
            f"{student.first_name} {student.last_name}",
            student.guardian_phone,
            float(fee.amount),
            primary_term,
            receipt,
        )

    return new_fee


@router.post("/other", response_model=schemas.FeeResponse)
def record_other_payment(
    payload: schemas.OtherFeePaymentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Record a payment for a fee-receipt line item with no arrears concept
    (Admission, Diary, Lunch, Computer, Tour, Medical, Graduation,
    Miscellaneous, ...). Deliberately flat, like activities.record_activity_
    payment — does NOT go through the tuition waterfall in record_payment,
    which would misfile it against tuition arrears instead of just logging
    what was paid for this specific item."""
    if current_user.role not in {"accountant", "admin", "secretary", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized to record payments")

    student = db.query(models.Student).filter(
        models.Student.id == payload.student_id,
        models.Student.is_deleted == False,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    receipt = _generate_receipt_number(db)
    new_fee = models.FeePayment(
        student_id=payload.student_id,
        amount=payload.amount,
        payment_type="Other",
        term=payload.term.value,
        activity=payload.fee_item,
        recorded_by=current_user.name,
        receipt_number=receipt,
        **({"payment_date": payload.payment_date} if payload.payment_date else {}),
    )
    db.add(new_fee)
    db.flush()
    log_action(db, current_user.id, "CREATE", "fee", new_fee.id,
               {"receipt": receipt, "amount": str(payload.amount), "student_id": payload.student_id,
                "fee_item": payload.fee_item})
    db.commit()
    db.refresh(new_fee)

    if student.guardian_phone:
        background_tasks.add_task(
            notify_payment,
            f"{student.first_name} {student.last_name}",
            student.guardian_phone,
            float(payload.amount),
            f"{payload.fee_item} ({payload.term.value})",
            receipt,
        )

    return new_fee


@router.get("/student/{student_id}", response_model=list[schemas.FeeResponse])
def get_student_payments(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to view fee records")
    student = db.query(models.Student).filter(
        models.Student.id == student_id,
        models.Student.is_deleted == False,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return (
        db.query(models.FeePayment)
        .filter(models.FeePayment.student_id == student_id)
        .order_by(models.FeePayment.payment_date.desc())
        .all()
    )


@router.get("/", response_model=list[schemas.FeeResponse])
def get_all_payments(
    skip: int = 0,
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to view financials")
    return (
        db.query(models.FeePayment)
        .order_by(models.FeePayment.payment_date.desc())
        .offset(skip).limit(limit).all()
    )


@router.get("/log")
def get_payment_log(
    limit: int = Query(default=500, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """All fee payments (active + voided) for the payment log statement.
    Voided payments are real rows (see void_payment) — kept for
    accountability rather than reconstructed from the audit log."""
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to view fee log")

    rows = (
        db.query(models.FeePayment, models.Student)
        .join(models.Student, models.FeePayment.student_id == models.Student.id)
        .order_by(models.FeePayment.payment_date.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id":               p.id,
            "status":           "voided" if p.is_voided else "active",
            "student_id":       p.student_id,
            "student_name":     f"{s.first_name} {s.last_name}",
            "admission_number": s.admission_number,
            "grade_level":      s.grade_level,
            "amount":           float(p.amount),
            "term":             p.term,
            "payment_type":     p.payment_type,
            "activity":         p.activity,
            "payment_date":     p.payment_date.isoformat() if p.payment_date else None,
            "receipt_number":   p.receipt_number,
            "recorded_by":      p.recorded_by,
            "voided_by":        p.voided_by,
            "voided_at":        p.voided_at.isoformat() if p.voided_at else None,
            "void_reason":      p.void_reason,
        }
        for p, s in rows
    ]


@router.post("/{payment_id}/void", response_model=schemas.FeeResponse)
def void_payment(
    payment_id: int,
    payload: schemas.VoidPaymentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Void a wrongly entered payment — a mistaken amount, wrong student,
    wrong fee item, whatever the reason. Restricted to admin and principal.

    Soft: the row stays (for accountability — a voided receipt is stamped
    void, not torn out), but is_voided is excluded from every arrears/
    collection calculation across fees.py, students.py and activities.py,
    so the student's balance and every reporting total correct themselves
    immediately. A reason is required and kept on the row itself, not just
    in the audit log, so it's visible wherever the payment is shown."""
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admin and principal can void fee payments")

    payment = db.query(models.FeePayment).filter(models.FeePayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.is_voided:
        raise HTTPException(status_code=400, detail="Payment is already voided")

    student = db.query(models.Student).filter(models.Student.id == payment.student_id).first()
    student_label = f"{student.first_name} {student.last_name} ({student.admission_number})" if student else f"student_id={payment.student_id}"

    payment.is_voided = True
    payment.voided_at = datetime.now()
    payment.voided_by = current_user.name
    payment.void_reason = payload.reason

    log_action(db, current_user.id, "UPDATE", "fee", payment_id, {
        "voided": True,
        "receipt_number": payment.receipt_number,
        "amount":         str(payment.amount),
        "term":           payment.term,
        "payment_type":   payment.payment_type,
        "activity":       payment.activity,
        "student":        student_label,
        "recorded_by":    payment.recorded_by,
        "reason":         payload.reason,
    })
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/balance/{student_id}/{term}")
def get_student_balance(
    student_id: int,
    term: str,
    academic_year: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to view financials")

    student = db.query(models.Student).filter(
        models.Student.id == student_id,
        models.Student.is_deleted == False,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    current_term_num = TERM_ORDER.get(term, 1)
    expected = _expected_fee_for_student(db, student, term)

    total_paid = float(
        db.query(func.sum(models.FeePayment.amount)).filter(
            models.FeePayment.student_id == student_id,
            models.FeePayment.term == term,
            models.FeePayment.activity.is_(None),
            models.FeePayment.is_voided == False,
        ).scalar() or 0.0
    )

    rollover_credit = _get_rollover_credit(db, student, current_term_num)
    carry_forward = _get_carry_forward(db, student_id, academic_year, term) if academic_year else 0.0

    outstanding = round(max(0.0, expected + carry_forward - total_paid - rollover_credit), 2)

    return {
        "student_id": student.id,
        "student_name": f"{student.first_name} {student.last_name}",
        "grade_level": student.grade_level,
        "term_checked": term,
        "expected_term_fee": expected,
        "carry_forward": carry_forward,
        "total_paid_this_term": total_paid,
        "rollover_credit": rollover_credit,
        "outstanding_balance": outstanding,
    }


@router.get("/term-summary")
def get_term_summary(
    term: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Expected vs collected for a given term across all active students."""
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to view financials")

    students = db.query(models.Student).filter(
        models.Student.is_deleted == False,
        models.Student.status == "Active",
    ).all()

    fee_map = _expected_fee_map(db)
    total_expected = round(sum(_expected_from_map_for_student(fee_map, s, term) for s in students), 2)

    # Effective collection: capped per-student so overpayments don't inflate %
    total_collected = compute_effective_term_collection(db, students, term)

    pct = round(total_collected / total_expected * 100, 1) if total_expected > 0 else 0.0

    return {
        "term": term,
        "total_expected": total_expected,
        "total_collected": total_collected,
        "percentage": pct,
    }


@router.get("/monthly-collection")
def get_monthly_collection(
    year: int = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Fee payments totalled by calendar month for a given year (defaults to current year)."""
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to view financials")

    if year is None:
        year = datetime.now().year

    rows = (
        db.query(
            func.extract("month", models.FeePayment.payment_date).label("month"),
            func.sum(models.FeePayment.amount).label("total"),
        )
        .filter(func.extract("year", models.FeePayment.payment_date) == year,
                models.FeePayment.is_voided == False)
        .group_by(func.extract("month", models.FeePayment.payment_date))
        .order_by(func.extract("month", models.FeePayment.payment_date))
        .all()
    )

    monthly = {int(r.month): float(r.total) for r in rows}
    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return [{"month": labels[m - 1], "total": monthly.get(m, 0.0)} for m in range(1, 13)]


@router.get("/defaulters")
def get_defaulters(
    term: str,
    academic_year: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return all active students who have an outstanding balance for the given term."""
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to view financials")

    current_term_num = TERM_ORDER.get(term, 1)
    year = datetime.now().year

    # ── 1. Load termly tuition structures for this year in one query ───────
    fee_map = _expected_fee_map(db)

    def expected_fee(s, t: str) -> float:
        return _expected_from_map_for_student(fee_map, s, t)

    # ── 2. Load all TUITION payments grouped by (student_id, term) ─────────
    # activity IS NULL excludes Transport/Co-curricular/Other — see _term_outstanding.
    pay_rows = db.query(
        models.FeePayment.student_id,
        models.FeePayment.term,
        func.sum(models.FeePayment.amount).label("total"),
    ).filter(
        models.FeePayment.activity.is_(None),
        models.FeePayment.is_voided == False,
    ).group_by(
        models.FeePayment.student_id, models.FeePayment.term
    ).all()
    paid_map = {(r.student_id, r.term): float(r.total) for r in pay_rows}

    # ── 3. Load carry-forwards for this academic year ──────────────────────
    cf_map: dict = {}
    if academic_year:
        cf_rows = db.query(
            models.FeeCarryForward.student_id,
            models.FeeCarryForward.term,
            func.sum(models.FeeCarryForward.amount).label("total"),
        ).filter(
            models.FeeCarryForward.academic_year == academic_year
        ).group_by(
            models.FeeCarryForward.student_id, models.FeeCarryForward.term
        ).all()
        cf_map = {(r.student_id, r.term): float(r.total) for r in cf_rows}

    # ── 4. Compute balances in Python (no more per-student queries) ─────────
    students = db.query(models.Student).filter(models.Student.is_deleted == False).all()
    prior_terms = [TERM_BY_NUM[n] for n in range(1, current_term_num)]

    defaulters = []
    for s in students:
        exp = expected_fee(s, term)
        if exp == 0:
            continue

        paid = paid_map.get((s.id, term), 0.0)
        carry_fwd = cf_map.get((s.id, term), 0.0)

        # Rollover: overpayment from all prior terms this year
        cum_exp = sum(expected_fee(s, t) for t in prior_terms)
        cum_paid = sum(paid_map.get((s.id, t), 0.0) for t in prior_terms)
        rollover = max(0.0, round(cum_paid - cum_exp, 2))

        balance = round(max(0.0, exp + carry_fwd - paid - rollover), 2)
        if balance > 0:
            # Full term-by-term breakdown up to and including the selected
            # term (every term still owing something) — lets the Defaulters
            # page print a one-page arrears invoice per student without any
            # further round trips, same shape as the receipt/statement view.
            term_breakdown = []
            running_cum_exp = running_cum_paid = 0.0
            for tnum in range(1, current_term_num + 1):
                t = TERM_BY_NUM[tnum]
                exp_t = expected_fee(s, t)
                paid_t = paid_map.get((s.id, t), 0.0)
                carry_t = cf_map.get((s.id, t), 0.0)
                rollover_t = max(0.0, round(running_cum_paid - running_cum_exp, 2))
                bal_t = round(max(0.0, exp_t + carry_t - paid_t - rollover_t), 2)
                if bal_t > 0:
                    term_breakdown.append({
                        "term": t, "expected": exp_t, "paid": paid_t,
                        "carry_forward": carry_t, "outstanding": bal_t,
                    })
                running_cum_exp += exp_t
                running_cum_paid += paid_t

            defaulters.append({
                "student_id": s.id,
                "student_name": f"{s.first_name} {s.last_name}",
                "admission_number": s.admission_number,
                "grade_level": s.grade_level,
                "expected_fee": exp,
                "carry_forward": carry_fwd,
                "total_paid": paid,
                "rollover_credit": rollover,
                "outstanding_balance": balance,
                "term_breakdown": term_breakdown,
                "total_arrears": round(sum(x["outstanding"] for x in term_breakdown), 2),
            })
    return defaulters


# ── Fee carry-forward CRUD ────────────────────────────────────────────────────

@router.get("/carry-forward/{student_id}", response_model=list[schemas.FeeCarryForwardResponse])
def get_carry_forwards(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")
    return db.query(models.FeeCarryForward).filter(
        models.FeeCarryForward.student_id == student_id,
    ).order_by(models.FeeCarryForward.academic_year, models.FeeCarryForward.term).all()


@router.post("/carry-forward", status_code=201, response_model=schemas.FeeCarryForwardResponse)
def create_carry_forward(
    payload: schemas.FeeCarryForwardCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")
    student = db.query(models.Student).filter(
        models.Student.id == payload.student_id,
        models.Student.is_deleted == False,
    ).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    cf = models.FeeCarryForward(
        **payload.model_dump(),
        recorded_by=current_user.name,
    )
    db.add(cf)
    db.flush()
    log_action(db, current_user.id, "CREATE", "fee_carry_forward", cf.id,
               {"student_id": payload.student_id, "amount": str(payload.amount),
                "year": payload.academic_year, "term": payload.term})
    db.commit()
    db.refresh(cf)
    return cf


@router.delete("/carry-forward/{cf_id}", status_code=204)
def delete_carry_forward(
    cf_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")
    cf = db.query(models.FeeCarryForward).filter(models.FeeCarryForward.id == cf_id).first()
    if not cf:
        raise HTTPException(status_code=404, detail="Not found")
    log_action(db, current_user.id, "DELETE", "fee_carry_forward", cf_id)
    db.delete(cf)
    db.commit()


# ── Fee Structure CRUD ────────────────────────────────────────────────────────

@router.get("/structure", response_model=list[schemas.FeeStructureResponse])
def get_fee_structure(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")
    return db.query(models.FeeStructure).order_by(
        models.FeeStructure.academic_year.desc(),
        models.FeeStructure.grade_level,
    ).all()


@router.get("/structure/template")
def get_fee_structure_template(
    year: int = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Default fee-structure rows for a year (the standard Bona School sheet),
    used to preload the editor when a year has no saved structure. Not persisted."""
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")
    return fee_structure_template_rows(year)


@router.post("/structure/bulk")
def bulk_upsert_fee_structure(
    entries: List[schemas.FeeStructureCreate],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Save the whole fee structure for a year in one go (principal/admin only).
    Upserts by (grade_level, term, fee_type, academic_year)."""
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admins and the principal can set the fee structure")
    if len(entries) > 500:
        raise HTTPException(status_code=400, detail="Too many entries in one request")

    saved = 0
    years = set()
    for e in entries:
        years.add(e.academic_year)
        row = db.query(models.FeeStructure).filter(
            models.FeeStructure.grade_level == e.grade_level,
            models.FeeStructure.term == e.term,
            models.FeeStructure.fee_type == e.fee_type,
            models.FeeStructure.academic_year == e.academic_year,
        ).first()
        if row:
            row.amount = e.amount
        else:
            db.add(models.FeeStructure(**e.model_dump()))
        saved += 1

    log_action(db, current_user.id, "UPDATE", "fee_structure", None,
               {"bulk": saved, "years": sorted(years)})
    db.commit()
    return {"saved": saved}


@router.post("/structure", response_model=schemas.FeeStructureResponse)
def create_fee_structure(
    entry: schemas.FeeStructureCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admins and the principal can configure fee structures")

    existing = db.query(models.FeeStructure).filter(
        models.FeeStructure.grade_level == entry.grade_level,
        models.FeeStructure.term == entry.term,
        models.FeeStructure.fee_type == entry.fee_type,
        models.FeeStructure.academic_year == entry.academic_year,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Fee structure entry already exists for this grade/term/type/year")

    new_entry = models.FeeStructure(**entry.model_dump())
    db.add(new_entry)
    db.flush()
    log_action(db, current_user.id, "CREATE", "fee_structure", new_entry.id, entry.model_dump())
    db.commit()
    db.refresh(new_entry)
    return new_entry


@router.put("/structure/{entry_id}", response_model=schemas.FeeStructureResponse)
def update_fee_structure(
    entry_id: int,
    entry: schemas.FeeStructureCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admins and the principal can configure fee structures")

    row = db.query(models.FeeStructure).filter(models.FeeStructure.id == entry_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Fee structure entry not found")

    for key, value in entry.model_dump().items():
        setattr(row, key, value)

    log_action(db, current_user.id, "UPDATE", "fee_structure", entry_id, entry.model_dump())
    db.commit()
    db.refresh(row)
    return row


@router.post("/bulk", status_code=201)
def record_bulk_payments(
    payments: List[schemas.BulkPaymentItem],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"accountant", "admin", "secretary", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized to record payments")
    if len(payments) > 500:
        raise HTTPException(status_code=400, detail="Bulk limit is 500 payments per request")

    student_ids = [p.student_id for p in payments]
    students_by_id = {
        s.id: s
        for s in db.query(models.Student).filter(
            models.Student.id.in_(student_ids),
            models.Student.is_deleted == False,
        ).all()
    }

    created = []
    for p in payments:
        student = students_by_id.get(p.student_id)
        if not student:
            continue
        current_term = str(getattr(p.term, "value", p.term))
        if _term_index(current_term) < 0:
            continue

        # Same waterfall as single payments: clear the oldest arrears first,
        # then the selected (current) term; any excess is a prepayment that
        # offsets the following terms' balances. Autoflush makes earlier rows
        # in this batch visible, so the same student can appear twice.
        allocation, _total_before, _advance = _compute_allocation(
            db, student, float(p.amount), current_term
        )
        primary_term = allocation[0]["term"]

        receipt = _generate_receipt_number(db)
        new_fee = models.FeePayment(
            student_id=p.student_id,
            amount=p.amount,
            payment_type=p.payment_type,
            term=primary_term,
            recorded_by=current_user.name,
            receipt_number=receipt,
            allocation=json.dumps(allocation),
            **({"payment_date": p.payment_date} if p.payment_date else {}),
        )
        db.add(new_fee)
        db.flush()
        log_action(db, current_user.id, "CREATE", "fee", new_fee.id,
                   {"receipt": receipt, "amount": str(p.amount), "student_id": p.student_id,
                    "allocation": allocation})
        created.append(new_fee.id)

    db.commit()
    return {"created": len(created)}


@router.delete("/structure/{entry_id}")
def delete_fee_structure(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"admin"}:
        raise HTTPException(status_code=403, detail="Only admins can delete fee structure entries")

    row = db.query(models.FeeStructure).filter(models.FeeStructure.id == entry_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Fee structure entry not found")

    log_action(db, current_user.id, "DELETE", "fee_structure", entry_id)
    db.delete(row)
    db.commit()
    return {"message": "Fee structure entry deleted"}


@router.get("/collection-summary")
def collection_summary(
    academic_year: Optional[str] = Query(None),
    term: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # Revenue totals by term — same "what the school makes" sensitivity as
    # dashboard net revenue, so the same restricted set (not the broader
    # FINANCE_ROLES, which includes secretary for fee-entry purposes).
    # Matches the frontend, which already gates /reports to admin/isFinance —
    # this was previously unenforced server-side, reachable by any logged-in
    # role via a direct API call regardless of what the UI hid.
    if current_user.role not in {"admin", "principal", "accountant"}:
        raise HTTPException(status_code=403, detail="Not authorized")

    from sqlalchemy import extract
    q = db.query(
        models.FeePayment.term,
        func.sum(models.FeePayment.amount).label("total_paid"),
        func.count(models.FeePayment.id).label("num_payments"),
        func.count(func.distinct(models.FeePayment.student_id)).label("unique_students"),
    ).filter(models.FeePayment.is_voided == False)
    if academic_year:
        try:
            q = q.filter(extract("year", models.FeePayment.payment_date) == int(academic_year))
        except (ValueError, TypeError):
            pass
    if term:
        q = q.filter(models.FeePayment.term == term)
    rows = q.group_by(models.FeePayment.term).order_by(models.FeePayment.term).all()
    return [
        {
            "term": r.term,
            "total_paid": round(float(r.total_paid or 0), 2),
            "num_payments": r.num_payments,
            "unique_students": r.unique_students,
        }
        for r in rows
    ]
