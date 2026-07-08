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


def _get_rollover_credit(db: Session, student_id: int, grade_level: str, up_to_term_num: int) -> float:
    """Return the cumulative overpayment from all terms before up_to_term_num (within same year)."""
    cumulative_expected = 0.0
    cumulative_paid = 0.0
    for num in range(1, up_to_term_num):
        t = TERM_BY_NUM[num]
        cumulative_expected += _get_expected_fee(db, grade_level, t)
        paid = db.query(func.sum(models.FeePayment.amount)).filter(
            models.FeePayment.student_id == student_id,
            models.FeePayment.term == t,
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
    student-balance endpoint (expected + carry-forward − paid − prior rollover)."""
    expected = _get_expected_fee(db, student.grade_level, term)
    total_paid = float(
        db.query(func.sum(models.FeePayment.amount))
        .filter(
            models.FeePayment.student_id == student.id,
            models.FeePayment.term == term,
        )
        .scalar() or 0.0
    )
    term_num = TERM_ORDER.get(term, 1)
    rollover = _get_rollover_credit(db, student.id, student.grade_level, term_num)
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


def compute_effective_term_collection(db: Session, students: list, term: str) -> float:
    """
    Compute the portion of payments that count toward `term`.

    Each student's contribution is capped at their expected fee for the term.
    Overpayments from prior terms are brought in as rollover credit before capping.
    This prevents overpayments in Term 1 from inflating Term 1's completion %.
    """
    term_num = TERM_ORDER.get(term, 1)
    total = 0.0
    for s in students:
        expected = _get_expected_fee(db, s.grade_level, term)
        if expected <= 0:
            continue
        direct_paid = float(
            db.query(func.sum(models.FeePayment.amount))
            .filter(models.FeePayment.student_id == s.id, models.FeePayment.term == term)
            .scalar() or 0.0
        )
        rollover = _get_rollover_credit(db, s.id, s.grade_level, term_num)
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

    for term in allowed_terms:
        paid = float(
            db.query(func.sum(models.FeePayment.amount))
            .filter(models.FeePayment.student_id == student_id, models.FeePayment.term == term)
            .scalar() or 0
        )
        expected = _get_expected_fee(db, None, term)  # grade resolved below
        student = db.query(models.Student).filter(models.Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        expected = _get_expected_fee(db, student.grade_level, term)
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
    """
    All fee payments (active + deleted) for the payment log statement.
    Active records come from the FeePayment table.
    Deleted records are reconstructed from the audit_logs (action=DELETE, resource=fee).
    """
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to view fee log")

    # ── Active payments ───────────────────────────────────────────────────────
    active_rows = (
        db.query(models.FeePayment, models.Student)
        .join(models.Student, models.FeePayment.student_id == models.Student.id)
        .order_by(models.FeePayment.payment_date.desc())
        .limit(limit)
        .all()
    )
    result = [
        {
            "id":               p.id,
            "status":           "active",
            "student_id":       p.student_id,
            "student_name":     f"{s.first_name} {s.last_name}",
            "admission_number": s.admission_number,
            "grade_level":      s.grade_level,
            "amount":           float(p.amount),
            "term":             p.term,
            "payment_type":     p.payment_type,
            "payment_date":     p.payment_date.isoformat() if p.payment_date else None,
            "receipt_number":   p.receipt_number,
            "recorded_by":      p.recorded_by,
            "deleted_by":       None,
            "deleted_at":       None,
        }
        for p, s in active_rows
    ]

    # ── Deleted payments (reconstructed from audit log) ───────────────────────
    deleted_rows = (
        db.query(models.AuditLog, models.User)
        .outerjoin(models.User, models.AuditLog.user_id == models.User.id)
        .filter(
            models.AuditLog.action   == "DELETE",
            models.AuditLog.resource == "fee",
        )
        .order_by(models.AuditLog.timestamp.desc())
        .all()
    )
    for log, deleter in deleted_rows:
        try:
            detail = json.loads(log.detail) if log.detail else {}
        except Exception:
            detail = {}

        # Determine friendly deleter label
        if deleter:
            role_label = deleter.role.replace("_", " ").title()
            deleted_by = f"{role_label} ({deleter.name})"
        else:
            deleted_by = "Unknown"

        # Parse student label stored as "First Last (BONA-0001)"
        student_raw = detail.get("student", "")
        student_name = student_raw.split("(")[0].strip() if "(" in student_raw else student_raw
        adm = student_raw[student_raw.find("(")+1:student_raw.find(")")] if "(" in student_raw else ""

        try:
            amount = float(detail.get("amount", 0))
        except (ValueError, TypeError):
            amount = 0.0

        result.append({
            "id":               f"del_{log.id}",
            "status":           "deleted",
            "student_id":       None,
            "student_name":     student_name or "Unknown",
            "admission_number": adm,
            "grade_level":      "",
            "amount":           amount,
            "term":             detail.get("term", ""),
            "payment_type":     detail.get("payment_type", ""),
            "payment_date":     None,
            "receipt_number":   detail.get("receipt_number"),
            "recorded_by":      detail.get("recorded_by", ""),
            "deleted_by":       deleted_by,
            "deleted_at":       log.timestamp.isoformat() if log.timestamp else None,
        })

    # Sort combined list — active by payment_date, deleted by deleted_at (latest first)
    def sort_key(r):
        ts = r["payment_date"] or r["deleted_at"] or ""
        return ts

    result.sort(key=sort_key, reverse=True)
    return result


@router.delete("/{payment_id}", status_code=204)
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Delete a wrongfully logged fee payment. Restricted to admin and principal. Deletion is audited."""
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Only admin and principal can delete fee payments")

    payment = db.query(models.FeePayment).filter(models.FeePayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    student = db.query(models.Student).filter(models.Student.id == payment.student_id).first()
    student_label = f"{student.first_name} {student.last_name} ({student.admission_number})" if student else f"student_id={payment.student_id}"

    log_action(db, current_user.id, "DELETE", "fee", payment_id, {
        "receipt_number": payment.receipt_number,
        "amount":         str(payment.amount),
        "term":           payment.term,
        "payment_type":   payment.payment_type,
        "student":        student_label,
        "recorded_by":    payment.recorded_by,
        "reason":         "manual_deletion_by_admin",
    })
    db.delete(payment)
    db.commit()


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
    expected = _get_expected_fee(db, student.grade_level, term)

    total_paid = float(
        db.query(func.sum(models.FeePayment.amount)).filter(
            models.FeePayment.student_id == student_id,
            models.FeePayment.term == term,
        ).scalar() or 0.0
    )

    rollover_credit = _get_rollover_credit(db, student_id, student.grade_level, current_term_num)
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

    total_expected = round(sum(_get_expected_fee(db, s.grade_level, term) for s in students), 2)

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
        .filter(func.extract("year", models.FeePayment.payment_date) == year)
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
    fee_structs = {
        (fs.grade_level, fs.term): float(fs.amount)
        for fs in db.query(models.FeeStructure)
        .filter(
            models.FeeStructure.academic_year == year,
            models.FeeStructure.fee_type == "Tuition",
        ).all()
    }

    def expected_fee(grade: str, t: str) -> float:
        return fee_structs.get((grade, t), CBC_TERMLY_FEES_FALLBACK.get(grade, 0.0))

    # ── 2. Load all payments grouped by (student_id, term) ─────────────────
    pay_rows = db.query(
        models.FeePayment.student_id,
        models.FeePayment.term,
        func.sum(models.FeePayment.amount).label("total"),
    ).group_by(models.FeePayment.student_id, models.FeePayment.term).all()
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
        exp = expected_fee(s.grade_level, term)
        if exp == 0:
            continue

        paid = paid_map.get((s.id, term), 0.0)
        carry_fwd = cf_map.get((s.id, term), 0.0)

        # Rollover: overpayment from all prior terms this year
        cum_exp = sum(expected_fee(s.grade_level, t) for t in prior_terms)
        cum_paid = sum(paid_map.get((s.id, t), 0.0) for t in prior_terms)
        rollover = max(0.0, round(cum_paid - cum_exp, 2))

        balance = round(max(0.0, exp + carry_fwd - paid - rollover), 2)
        if balance > 0:
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
    valid_students = db.query(models.Student.id).filter(
        models.Student.id.in_(student_ids),
        models.Student.is_deleted == False
    ).all()
    valid_student_ids = {s[0] for s in valid_students}

    created = []
    for p in payments:
        if p.student_id not in valid_student_ids:
            continue
        receipt = _generate_receipt_number(db)
        new_fee = models.FeePayment(
            student_id=p.student_id,
            amount=p.amount,
            payment_type=p.payment_type,
            term=p.term,
            recorded_by=current_user.name,
            receipt_number=receipt,
        )
        db.add(new_fee)
        db.flush()
        log_action(db, current_user.id, "CREATE", "fee", new_fee.id,
                   {"receipt": receipt, "amount": str(p.amount), "student_id": p.student_id})
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
    from sqlalchemy import extract
    q = db.query(
        models.FeePayment.term,
        func.sum(models.FeePayment.amount).label("total_paid"),
        func.count(models.FeePayment.id).label("num_payments"),
        func.count(func.distinct(models.FeePayment.student_id)).label("unique_students"),
    )
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
