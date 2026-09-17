"""JWT + password hashing + role-based access decorators."""
import functools
from datetime import datetime, timezone

import bcrypt
import jwt
from bson import ObjectId
from bson.errors import InvalidId
from flask import g, jsonify, request

from config import config
from models import db


# ---------------- Password hashing (bcrypt) ----------------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------- JWT ----------------
def create_access_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["_id"]),
        "email": user["email"],
        "role": user["role"],
        "name": user.get("name", ""),
        "iat": now,
        "exp": now + config.JWT_ACCESS_TTL,
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])


def _extract_token() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1].strip()
    return None


# ---------------- Decorators ----------------
def jwt_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Authorization token missing"}), 401
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        try:
            user = db.users().find_one({"_id": ObjectId(payload["sub"])})
        except (InvalidId, KeyError):
            user = None
        if not user:
            return jsonify({"error": "User no longer exists"}), 401

        g.current_user = user
        g.jwt_payload = payload
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*allowed_roles):
    def decorator(fn):
        @functools.wraps(fn)
        @jwt_required
        def wrapper(*args, **kwargs):
            if g.current_user["role"] not in allowed_roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


admin_required = roles_required("admin")
lecturer_required = roles_required("lecturer", "admin")
