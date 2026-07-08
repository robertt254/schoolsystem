import json
import models
from sqlalchemy.orm import Session


def log_action(
    db: Session,
    user_id: int,
    action: str,
    resource: str,
    resource_id: int = None,
    detail: dict = None,
) -> None:
    """
    Append an immutable audit log entry.
    Call this inside the same transaction as the write operation so both
    either commit or roll back together.
    """
    entry = models.AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        detail=json.dumps(detail, default=str) if detail else None,
    )
    db.add(entry)
