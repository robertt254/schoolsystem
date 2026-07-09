"""Database backups — the bridge for moving off Render to a locally hosted
database.

A backup is a single JSON snapshot of every table, portable across database
engines. Snapshots are written periodically by a background scheduler and can
be created/listed/downloaded on demand — all restricted to the ONE system
administrator. Restore into a local database with `restore_backup.py`.

Environment:
    BACKUP_ENABLED         "true" (default) — set "false" to disable the scheduler
    BACKUP_INTERVAL_HOURS  hours between periodic snapshots (default 24)
    BACKUP_KEEP            how many snapshots to retain (default 7)
    BACKUP_DIR             where snapshots are written (default backend/backups)

Note: on Render's free tier the container disk is ephemeral — snapshots are
lost on redeploy, which is why download-and-keep-locally is the point. The
real data always lives in Postgres; a fresh snapshot can be generated at any
moment from the Admin page.
"""
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, date, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db, Base, SessionLocal
import models  # noqa: F401 — ensures every table is registered on Base
import auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/backups", tags=["Backups"])

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", str(Path(__file__).resolve().parent / "backups")))
BACKUP_INTERVAL_HOURS = float(os.getenv("BACKUP_INTERVAL_HOURS", "24"))
BACKUP_KEEP = int(os.getenv("BACKUP_KEEP", "7"))

_FILENAME_RE = re.compile(r"^bns_backup_\d{8}T\d{6}Z\.json$")


def require_system_admin(current_user: models.User = Depends(auth.get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Backups are restricted to the system administrator")
    return current_user


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def create_backup(db: Session) -> Path:
    """Snapshot every table into one JSON file and prune old snapshots."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "format": 1,
        "system": "Bona School Kenya",
        "tables": {},
    }
    for table in Base.metadata.sorted_tables:
        rows = db.execute(table.select()).mappings().all()
        snapshot["tables"][table.name] = [dict(r) for r in rows]

    name = f"bns_backup_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}Z.json"
    path = BACKUP_DIR / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, default=_json_default)

    _prune_old_backups()
    return path


def _prune_old_backups():
    files = sorted(BACKUP_DIR.glob("bns_backup_*.json"))
    for old in files[:-BACKUP_KEEP]:
        old.unlink(missing_ok=True)


# ── Endpoints (system admin only) ─────────────────────────────────────────────

@router.get("/")
def list_backups(current_user: models.User = Depends(require_system_admin)):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(BACKUP_DIR.glob("bns_backup_*.json"), reverse=True)
    return [
        {
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "created_at": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
        }
        for f in files
    ]


@router.post("/", status_code=201)
def create_backup_now(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_system_admin),
):
    path = create_backup(db)
    logger.info("Manual backup created by %s: %s", current_user.username, path.name)
    return {"filename": path.name, "size_bytes": path.stat().st_size}


@router.get("/{filename}")
def download_backup(
    filename: str,
    current_user: models.User = Depends(require_system_admin),
):
    # Strict filename allowlist prevents any path traversal
    if not _FILENAME_RE.match(filename):
        raise HTTPException(status_code=404, detail="Backup not found")
    path = (BACKUP_DIR / filename).resolve()
    if not str(path).startswith(str(BACKUP_DIR.resolve())) or not path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(path, media_type="application/json", filename=filename)


# ── Periodic scheduler ─────────────────────────────────────────────────────────

def start_backup_scheduler():
    """Write a snapshot every BACKUP_INTERVAL_HOURS in a daemon thread."""
    if os.getenv("BACKUP_ENABLED", "true").lower() not in {"1", "true", "yes"}:
        logger.info("Periodic backups disabled (BACKUP_ENABLED).")
        return

    def _loop():
        interval = max(BACKUP_INTERVAL_HOURS, 0.1) * 3600
        while True:
            time.sleep(interval)
            try:
                with SessionLocal() as db:
                    path = create_backup(db)
                logger.info("Periodic backup written: %s", path.name)
            except Exception as exc:
                logger.warning("Periodic backup failed: %s", exc)

    threading.Thread(target=_loop, daemon=True, name="backup-scheduler").start()
    logger.info("Periodic backups every %s h (keeping last %s) in %s",
                BACKUP_INTERVAL_HOURS, BACKUP_KEEP, BACKUP_DIR)
