"""Tests for the finance endpoints: expenses, budgets, petty cash, payroll."""
import models


# ── Expenses ───────────────────────────────────────────────────────────────────

def test_create_and_list_expense(as_admin):
    r = as_admin.post("/api/finance/expenses", json={
        "amount": 2500, "category": "Utilities", "justification": "Water bill"})
    assert r.status_code == 200
    body = r.json()
    assert body["amount"] == 2500
    assert body["recorded_by"]

    r = as_admin.get("/api/finance/expenses")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["justification"] == "Water bill"


def test_create_expense_forbidden_for_accountant(as_accountant):
    r = as_accountant.post("/api/finance/expenses", json={
        "amount": 100, "justification": "Should not work"})
    assert r.status_code == 403


# ── Budgets ────────────────────────────────────────────────────────────────────

def test_budget_lifecycle_with_actuals(as_admin):
    # Create a budget line
    r = as_admin.post("/api/finance/budget", json={
        "category": "Utilities", "academic_year": 2026,
        "term": "Term 1", "budgeted_amount": 30000})
    assert r.status_code == 201
    budget_id = r.json()["id"]

    # Record a matching expense so actual_spent is non-zero
    as_admin.post("/api/finance/expenses", json={
        "amount": 5000, "category": "Utilities", "justification": "Electricity"})

    r = as_admin.get("/api/finance/budget", params={"academic_year": 2026})
    assert r.status_code == 200
    line = next(b for b in r.json() if b["id"] == budget_id)
    assert line["budgeted_amount"] == 30000
    assert line["actual_spent"] == 5000
    assert line["variance"] == 25000

    # Update
    r = as_admin.put(f"/api/finance/budget/{budget_id}", json={
        "category": "Utilities", "academic_year": 2026,
        "term": "Term 1", "budgeted_amount": 40000})
    assert r.status_code == 200

    # Delete
    r = as_admin.delete(f"/api/finance/budget/{budget_id}")
    assert r.status_code == 204
    r = as_admin.get("/api/finance/budget", params={"academic_year": 2026})
    assert all(b["id"] != budget_id for b in r.json())


def test_update_missing_budget_404(as_admin):
    r = as_admin.put("/api/finance/budget/999", json={
        "category": "X", "academic_year": 2026, "term": "Term 1", "budgeted_amount": 1})
    assert r.status_code == 404


# ── Petty cash ─────────────────────────────────────────────────────────────────

def test_petty_cash_running_balance_and_delete(as_admin):
    r = as_admin.post("/api/finance/petty-cash", json={
        "transaction_type": "IN", "amount": 10000, "description": "Top-up"})
    assert r.status_code == 201
    r = as_admin.post("/api/finance/petty-cash", json={
        "transaction_type": "OUT", "amount": 1500, "description": "Stationery"})
    assert r.status_code == 201
    tx_id = r.json()["id"]

    r = as_admin.get("/api/finance/petty-cash")
    assert r.status_code == 200
    ledger = r.json()  # newest first
    assert ledger[0]["running_balance"] == 8500
    assert ledger[1]["running_balance"] == 10000

    r = as_admin.delete(f"/api/finance/petty-cash/{tx_id}")
    assert r.status_code == 204
    r = as_admin.get("/api/finance/petty-cash")
    assert r.json()[0]["running_balance"] == 10000


# ── Payroll ────────────────────────────────────────────────────────────────────

def _add_staff(db_session, username, salary):
    from auth import get_password_hash
    staff = models.User(
        username=username, hashed_password=get_password_hash("irrelevant-pw"),
        name=username.title(), role="teacher", basic_salary=salary,
        allowances=0, deductions=0, can_login=False,
    )
    db_session.add(staff)
    db_session.commit()
    db_session.refresh(staff)
    return staff


def test_payroll_run_month_and_payslip(as_admin, db_session):
    staff = _add_staff(db_session, "paid_teacher", 30000)

    # Preview shows the staff member as unpaid
    r = as_admin.get("/api/finance/payroll/monthly", params={"month": "2026-07"})
    assert r.status_code == 200
    entry = next(p for p in r.json()["preview"] if p["staff_id"] == staff.id)
    assert entry["already_paid"] is False
    assert entry["net_pay"] == 30000

    # Run payroll for that staff member
    r = as_admin.post("/api/finance/payroll/run-month", json={
        "month": "2026-07",
        "entries": [{"staff_id": staff.id, "allowances": 2000, "deductions": 500}]})
    assert r.status_code == 201
    assert r.json()["created"] == 1

    # Now marked paid, with a payslip in history
    r = as_admin.get("/api/finance/payroll/monthly", params={"month": "2026-07"})
    entry = next(p for p in r.json()["preview"] if p["staff_id"] == staff.id)
    assert entry["already_paid"] is True
    slip = r.json()["history"][0]
    assert slip["net_pay"] == 31500

    r = as_admin.get(f"/api/finance/payslip/{slip['id']}")
    assert r.status_code == 200
    assert r.json()["staff_name"] == staff.name

    # Re-running the same month skips instead of double-paying
    r = as_admin.post("/api/finance/payroll/run-month", json={
        "month": "2026-07", "entries": [{"staff_id": staff.id}]})
    assert r.json()["created"] == 0
    assert r.json()["skipped"] == 1


def test_payroll_skips_staff_without_salary(as_admin, db_session):
    staff = _add_staff(db_session, "unpaid_helper", 0)
    r = as_admin.post("/api/finance/payroll/run-month", json={
        "month": "2026-07", "entries": [{"staff_id": staff.id}]})
    assert r.status_code == 201
    assert r.json()["created"] == 0
    assert staff.name in r.json()["skipped_names"]


def test_void_payroll_month_admin_only(as_admin, as_accountant, db_session):
    # as_accountant fixture overrode the current user last → active user is accountant
    r = as_accountant.delete("/api/finance/payroll/monthly", params={"month": "2026-07"})
    assert r.status_code == 403


def test_void_payroll_month(as_admin, db_session):
    staff = _add_staff(db_session, "voided_teacher", 20000)
    as_admin.post("/api/finance/payroll/run-month", json={
        "month": "2026-08", "entries": [{"staff_id": staff.id}]})

    r = as_admin.delete("/api/finance/payroll/monthly", params={"month": "2026-08"})
    assert r.status_code == 204

    r = as_admin.get("/api/finance/payroll/monthly", params={"month": "2026-08"})
    assert r.json()["history"] == []
