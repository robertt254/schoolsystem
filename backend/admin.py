"""Administrative maintenance endpoints — system-admin only."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
import models, auth
from audit import log_action

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# Table names are interpolated into TRUNCATE/COUNT statements (they cannot be
# bound parameters). Defense in depth: even though every name comes from the
# fixed allow-lists below, reject anything that is not a plain identifier so a
# future change can never turn this into an injection vector.
_SAFE_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def _validated(tables: list[str]) -> list[str]:
    bad = [t for t in tables if not _SAFE_IDENTIFIER.fullmatch(t)]
    if bad:
        raise ValueError(f"Unsafe table identifier(s): {bad}")
    return tables

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
    targets = _validated([t for t in wanted if t in existing])  # preserve order, only existing
    if not targets:
        return {"cleared": {}}

    # Row counts before wiping. Identifiers pass _validated() above and come
    # from the fixed allow-lists — never from request input.
    cleared = {t: db.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in targets}

    db.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in targets) + " RESTART IDENTITY CASCADE"))
    # audit_logs was just truncated; this becomes the first new entry — a record
    # that the reset happened, by whom.
    log_action(db, current_user.id, "RESET", "database", None,
               {"cleared": cleared, "with_finance": payload.with_finance})
    db.commit()
    return {"cleared": cleared}
