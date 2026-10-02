from sqlalchemy.orm import Session
from app import models


def log_action(db: Session, actor: str, action: str, details: str | None = None):
    """Record one step. actor is 'ai', 'human', or 'system'."""
    entry = models.AuditLog(actor=actor, action=action, details=details)
    db.add(entry)
    db.commit()
    return entry