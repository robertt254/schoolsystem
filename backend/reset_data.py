"""
One-shot data reset for The Bona School.

Clears operational records so a new period can start on a clean slate, while
KEEPING configuration and logins: users/staff, fee structure, term dates,
subjects, library catalogue, calendar events, budgets, etc.

What it clears:
  - students  (and everything linked to a student by foreign key: grades,
    attendance, discipline records, exam results, library borrows)
  - fee payments and fee carry-forwards (the data behind fee statements)
  - audit / activity logs
  Optionally, with --with-finance, also: expenses, payroll, petty cash.

Safety:
  - Dry run by default — it only prints what WOULD be deleted.
  - Pass --yes to actually wipe.
  - Only truncates tables that exist (safe across deploys).
  - Targets whatever DATABASE_URL points to — on Render that is the live DB,
    so double-check before using --yes.

Usage (from the backend directory, e.g. the Render web-service Shell tab):
    python reset_data.py                  # dry run, shows counts
    python reset_data.py --yes            # wipe students/fees/logs
    python reset_data.py --yes --with-finance   # also zero expenses/payroll/petty cash
"""
import re
import sys

from sqlalchemy import text

from database import engine

# Identifiers are interpolated into SQL (TRUNCATE/COUNT take no bind params).
# Validate them even though they come from the fixed lists below, so a future
# edit can never turn this into an injection vector.
_SAFE_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")

# Order is illustrative only; TRUNCATE ... CASCADE handles dependencies.
CORE_TABLES = [
    "fees",                  # fee payments
    "fee_carry_forwards",    # balance carry-forwards (feed statements)
    "assessments",           # grades (linked to students)
    "attendance",            # linked to students
    "disciplinary_records",  # linked to students
    "exam_results",          # linked to students
    "library_borrows",       # linked to students
    "audit_logs",            # activity / audit logs
    "students",
]
FINANCE_EXTRA = ["expenses", "payroll", "petty_cash"]


def _existing(conn, names):
    rows = conn.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = ANY(:names)"
        ),
        {"names": names},
    ).fetchall()
    found = {r[0] for r in rows}
    return [n for n in names if n in found]  # preserve declared order


def main() -> None:
    confirm = "--yes" in sys.argv
    with_finance = "--with-finance" in sys.argv

    targets = CORE_TABLES + (FINANCE_EXTRA if with_finance else [])

    with engine.connect() as conn:
        tables = _existing(conn, targets)
        bad = [t for t in tables if not _SAFE_IDENTIFIER.fullmatch(t)]
        if bad:
            print(f"Refusing to run: unsafe table identifier(s) {bad}")
            return
        if not tables:
            print("No matching tables found — nothing to do.")
            return

        print("Tables to clear and current row counts:")
        for t in tables:
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
            print(f"  {t:<22} {count:>8}")

        if not confirm:
            print("\nDRY RUN - nothing was deleted.")
            print("Re-run with --yes to wipe (add --with-finance to also clear "
                  "expenses/payroll/petty cash).")
            return

        # All names come from the fixed allow-lists above (no user input) and
        # were validated against _SAFE_IDENTIFIER before interpolation.
        conn.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))
        conn.commit()
        print("\nDone - listed tables truncated and ID/receipt counters reset to 1.")
        print("Configuration and user logins were left intact.")


if __name__ == "__main__":
    main()
