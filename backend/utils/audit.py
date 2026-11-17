"""Audit logging helper (safe inside or outside Flask application context)."""
from flask import g, has_app_context, has_request_context, request

from models import db


def log_action(action: str, **extra):
    user = None
    ip = None
    path = None

    if has_app_context():
        user = getattr(g, "current_user", None)
    if has_request_context():
        ip = getattr(request, "remote_addr", None)
        path = getattr(request, "path", None)

    entry = {
        "user_id": str(user["_id"]) if user else extra.get("user_id"),
        "user_email": user["email"] if user else extra.get("user_email"),
        "action": action,
        "ip": ip,
        "path": path,
        "timestamp": db.utcnow(),
    }
    entry.update(extra)
    db.audit_logs().insert_one(entry)
    return entry
