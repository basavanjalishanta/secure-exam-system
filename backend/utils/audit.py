"""Audit logging helper."""
from flask import g, request

from models import db


def log_action(action: str, **extra):
    user = getattr(g, "current_user", None)
    entry = {
        "user_id": str(user["_id"]) if user else None,
        "user_email": user["email"] if user else None,
        "action": action,
        "ip": request.remote_addr if request else None,
        "path": request.path if request else None,
        "timestamp": db.utcnow(),
    }
    entry.update(extra)
    db.audit_logs().insert_one(entry)
    return entry
