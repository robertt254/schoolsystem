"""Administrative maintenance endpoints — system-admin only."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
import models, auth
from audit import log_action

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# Operational data cleared on reset. Everything else (users/logins, fee
# structure, term dates, subjects, library catalogue, calendar, budgets) is kept.
# TRUNCATE ... CASCADE also clears anything else FK-linked to students.
_CORE_TABLES = [
    "fees",
    "fee_carry_forwards",
    "assessments",
    "attendance",
    "disciplinary_records",
    "exam_results",
    "library_borrows",
    "audit_logs",
    "students",
]
_FINANCE_EXTRA = ["expenses", "payroll", "petty_cash"]


class ResetRequest(BaseModel):
    confirm: str
    with_finance: bool = False


@router.post("/reset-data")
def reset_data(
    payload: ResetRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Wipe operational records for a clean slate. System-admin only; requires
    the literal confirmation text 'RESET'. Keeps logins and configuration."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only the system administrator can reset data")
    if (payload.confirm or "").strip().upper() != "RESET":
        raise HTTPException(status_code=400, detail="Type RESET to confirm this action")

    wanted = _CORE_TABLES + (_FINANCE_EXTRA if payload.with_finance else [])

    existing = {
        r[0] for r in db.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = ANY(:names)"
            ),
            {"names": wanted},
        ).fetchall()
    }
    targets = [t for t in wanted if t in existing]  # preserve order, only existing
    if not targets:
        return {"cleared": {}}

    # Row counts before wiping (names come from fixed allow-lists, not user input).
    cleared = {t: db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in targets}

    db.execute(text("TRUNCATE " + ", ".join(targets) + " RESTART IDENTITY CASCADE"))
    # audit_logs was just truncated; this becomes the first new entry — a record
    # that the reset happened, by whom.
    log_action(db, current_user.id, "RESET", "database", None,
               {"cleared": cleared, "with_finance": payload.with_finance})
    db.commit()
    return {"cleared": cleared}
