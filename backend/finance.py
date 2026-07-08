from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models, schemas, auth
from audit import log_action
from typing import Optional

router = APIRouter(prefix="/api/finance", tags=["Finance"])

FINANCE_ROLES = {"accountant", "admin", "principal"}
PAYROLL_ROLES = {"accountant", "admin"}


def require_finance(current_user: models.User = Depends(auth.get_current_user)):
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user


def require_payroll_manager(current_user: models.User = Depends(auth.get_current_user)):
    if current_user.role not in PAYROLL_ROLES:
        raise HTTPException(status_code=403, detail="Payroll is restricted to accountant and admin only")
    return current_user



@router.get("/payroll/monthly")
def get_payroll_monthly(
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_payroll_manager),
):
    """Returns all non-admin staff with salary data + already-paid status, plus paid records for the month."""
    staff_list = (
        db.query(models.User)
        .filter(models.User.role != "admin")
        .order_by(models.User.name)
        .all()
    )
    staff_map = {s.id: s for s in staff_list}

    paid_rows = (
        db.query(models.Payroll)
        .filter(models.Payroll.payment_month == month)
        .order_by(models.Payroll.id.desc())
        .all()
    )
    paid_ids = {p.staff_id for p in paid_rows if p.staff_id is not None}

    preview = []
    for s in staff_list:
        basic = float(s.basic_salary or 0)
        allow = float(s.allowances or 0)
        deduct = float(s.deductions or 0)
        net = max(0.0, basic + allow - deduct)
        preview.append({
            "staff_id": s.id,
            "staff_name": s.name,
            "role": s.role,
            "job_title": s.job_title or "",
            "basic_salary": basic,
            "allowances": allow,
            "deductions": deduct,
            "net_pay": net,
            "already_paid": s.id in paid_ids,
        })

    history = []
    for p in paid_rows:
        staff = staff_map.get(p.staff_id)
        history.append({
            "id": p.id,
            "staff_id": p.staff_id,
            "staff_name": staff.name if staff else f"Staff #{p.staff_id}",
            "payment_month": p.payment_month,
            "basic_salary": float(p.basic_salary),
            "allowances": float(p.allowances),
            "deductions": float(p.deductions),
            "net_pay": float(p.net_pay),
            "recorded_by": p.recorded_by,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return {"preview": preview, "history": history}


@router.delete("/payroll/monthly", status_code=204)
def void_payroll_month(
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_payroll_manager),
):
    """Delete all payroll records for a month. Restricted to admin only."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can void a payroll run")
    records = db.query(models.Payroll).filter(models.Payroll.payment_month == month).all()
    count = len(records)
    for r in records:
        db.delete(r)
    log_action(db, current_user.id, "DELETE", "payroll_batch", None,
               {"month": month, "voided_count": count})
    db.commit()


@router.post("/payroll/run-month", status_code=201)
def run_month_payroll(
    payload: schemas.RunPayrollRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_payroll_manager),
):
    """Execute payroll for submitted staff entries. Each payslip is logged individually."""
    if not payload.entries:
        raise HTTPException(status_code=400, detail="No staff entries provided")

    entry_map = {e.staff_id: e for e in payload.entries}
    staff_list = (
        db.query(models.User)
        .filter(models.User.id.in_(list(entry_map.keys())))
        .all()
    )

    existing_payrolls = (
        db.query(models.Payroll.staff_id)
        .filter(
            models.Payroll.staff_id.in_(list(entry_map.keys())),
            models.Payroll.payment_month == payload.month,
        )
        .with_for_update()
        .all()
    )
    existing_staff_ids = {row.staff_id for row in existing_payrolls}

    created_names, skipped_names = [], []
    for s in staff_list:
        basic = float(s.basic_salary or 0)
        if basic == 0:
            skipped_names.append(s.name)
            continue

        if s.id in existing_staff_ids:
            skipped_names.append(s.name)
            continue

        entry = entry_map[s.id]
        allow = max(0.0, float(entry.allowances))
        deduct = max(0.0, float(entry.deductions))
        net = max(0.0, basic + allow - deduct)

        p = models.Payroll(
            staff_id=s.id,
            payment_month=payload.month,
            basic_salary=basic,
            allowances=allow,
            deductions=deduct,
            net_pay=net,
            recorded_by=current_user.name,
        )
        db.add(p)
        db.flush()  # obtain p.id before logging

        role_label = s.job_title or s.role.replace("_", " ").title()
        log_action(db, current_user.id, "CREATE", "payroll", p.id, {
            "detail": f"Paid salary for {s.name} ({role_label})",
            "month": payload.month,
            "net_pay": str(round(net, 2)),
        })
        created_names.append(s.name)

    db.commit()
    return {
        "created": len(created_names),
        "skipped": len(skipped_names),
        "created_names": created_names,
        "skipped_names": skipped_names,
    }


@router.post("/expenses", response_model=schemas.ExpenseResponse)
def create_expense(
    expense: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in {"principal", "admin"}:
        raise HTTPException(status_code=403, detail="Only the principal or admin can record expenses")

    new_expense = models.Expense(
        **expense.model_dump(),
        recorded_by=current_user.name,
    )
    db.add(new_expense)
    db.flush()
    log_action(db, current_user.id, "CREATE", "expense", new_expense.id,
               {"amount": str(expense.amount), "category": expense.category})
    db.commit()
    db.refresh(new_expense)
    return new_expense


@router.get("/expenses", response_model=list[schemas.ExpenseResponse])
def get_expenses(
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role not in FINANCE_ROLES:
        raise HTTPException(status_code=403, detail="Not authorized to view expenses")
    return (
        db.query(models.Expense)
        .order_by(models.Expense.expense_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ── Payslip ────────────────────────────────────────────────────────────────────

@router.get("/payslip/{payroll_id}")
def get_payslip(
    payroll_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_payroll_manager),
):
    p = db.query(models.Payroll).filter(models.Payroll.id == payroll_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payroll record not found")

    staff = db.query(models.User).filter(models.User.id == p.staff_id).first()
    return {
        "id": p.id,
        "payment_month": p.payment_month,
        "basic_salary": float(p.basic_salary),
        "allowances": float(p.allowances),
        "deductions": float(p.deductions),
        "net_pay": float(p.net_pay),
        "recorded_by": p.recorded_by,
        "created_at": p.created_at,
        "staff_name": staff.name if staff else "Unknown",
        "job_title": staff.job_title if staff else None,
        "kra_pin": staff.kra_pin if staff else None,
        "nssf_number": staff.nssf_number if staff else None,
        "nhif_number": staff.nhif_number if staff else None,
    }


# ── Budget ─────────────────────────────────────────────────────────────────────

@router.get("/budget")
def get_budgets(
    academic_year: Optional[int] = Query(None),
    term: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_finance),
):
    q = db.query(models.Budget)
    if academic_year:
        q = q.filter(models.Budget.academic_year == academic_year)
    if term:
        q = q.filter(models.Budget.term == term)
    budgets = q.order_by(models.Budget.term, models.Budget.category).all()

    # One query for all actuals — avoids N queries (one per budget line)
    years = {b.academic_year for b in budgets}
    actuals_rows = (
        db.query(
            models.Expense.category,
            func.extract("year", models.Expense.expense_date).label("yr"),
            func.sum(models.Expense.amount).label("total"),
        )
        .filter(func.extract("year", models.Expense.expense_date).in_(years))
        .group_by(models.Expense.category, func.extract("year", models.Expense.expense_date))
        .all()
    )
    actuals_map = {(row.category, int(row.yr)): float(row.total) for row in actuals_rows}

    result = []
    for b in budgets:
        actual = actuals_map.get((b.category, b.academic_year), 0.0)
        variance = float(b.budgeted_amount) - actual
        result.append({
            "id": b.id,
            "category": b.category,
            "academic_year": b.academic_year,
            "term": b.term,
            "budgeted_amount": float(b.budgeted_amount),
            "actual_spent": round(actual, 2),
            "variance": round(variance, 2),
            "created_by": b.created_by,
        })
    return result


@router.post("/budget", status_code=201)
def create_budget(
    payload: schemas.BudgetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_finance),
):
    b = models.Budget(
        category=payload.category,
        academic_year=payload.academic_year,
        term=payload.term,
        budgeted_amount=payload.budgeted_amount,
        created_by=current_user.name,
    )
    db.add(b)
    db.flush()
    log_action(db, current_user.id, "CREATE", "budget", b.id,
               {"category": payload.category, "amount": str(payload.budgeted_amount)})
    db.commit()
    db.refresh(b)
    return {"id": b.id, "category": b.category, "academic_year": b.academic_year,
            "term": b.term, "budgeted_amount": float(b.budgeted_amount), "created_by": b.created_by}


@router.put("/budget/{budget_id}", status_code=200)
def update_budget(
    budget_id: int,
    payload: schemas.BudgetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_finance),
):
    b = db.query(models.Budget).filter(models.Budget.id == budget_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Budget not found")
    b.category = payload.category
    b.academic_year = payload.academic_year
    b.term = payload.term
    b.budgeted_amount = payload.budgeted_amount
    log_action(db, current_user.id, "UPDATE", "budget", budget_id)
    db.commit()
    return {"message": "Updated"}


@router.delete("/budget/{budget_id}", status_code=204)
def delete_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_finance),
):
    b = db.query(models.Budget).filter(models.Budget.id == budget_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Budget not found")
    log_action(db, current_user.id, "DELETE", "budget", budget_id)
    db.delete(b)
    db.commit()


# ── Petty Cash ─────────────────────────────────────────────────────────────────

@router.get("/petty-cash")
def get_petty_cash(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_finance),
):
    transactions = (
        db.query(models.PettyCashTransaction)
        .order_by(models.PettyCashTransaction.transaction_date.asc())
        .all()
    )
    running = 0.0
    result = []
    for t in transactions:
        amt = float(t.amount)
        running += amt if t.transaction_type == "IN" else -amt
        result.append({
            "id": t.id,
            "transaction_type": t.transaction_type,
            "amount": amt,
            "description": t.description,
            "category": t.category,
            "recorded_by": t.recorded_by,
            "transaction_date": t.transaction_date,
            "running_balance": round(running, 2),
        })
    result.reverse()
    return result


@router.post("/petty-cash", status_code=201)
def create_petty_cash(
    payload: schemas.PettyCashCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_finance),
):
    t = models.PettyCashTransaction(
        transaction_type=payload.transaction_type,
        amount=payload.amount,
        description=payload.description,
        category=payload.category,
        recorded_by=current_user.name,
        transaction_date=datetime.now(timezone.utc),
    )
    db.add(t)
    db.flush()
    log_action(db, current_user.id, "CREATE", "petty_cash", t.id,
               {"type": payload.transaction_type, "amount": str(payload.amount)})
    db.commit()
    return {"id": t.id, "message": "Recorded"}


@router.delete("/petty-cash/{tx_id}", status_code=204)
def delete_petty_cash(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_finance),
):
    if current_user.role not in {"admin", "principal"}:
        raise HTTPException(status_code=403, detail="Not authorized")
    t = db.query(models.PettyCashTransaction).filter(models.PettyCashTransaction.id == tx_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    log_action(db, current_user.id, "DELETE", "petty_cash", tx_id)
    db.delete(t)
    db.commit()
