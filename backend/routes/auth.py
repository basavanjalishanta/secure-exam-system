"""Authentication: register, login, logout, me."""
from flask import Blueprint, g, jsonify, request
import hashlib
import secrets
from datetime import timedelta, timezone
from utils.email_otp import send_login_otp

from models import db
from config import config
from utils.audit import log_action
from utils.security import (
    create_access_token,
    hash_password,
    jwt_required,
    verify_password,
)
from utils.serialization import jsonify_doc

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/register")
def register():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role", "lecturer")

    if not name or not email or len(password) < 8:
        return jsonify({"error": "name, email and a password of >= 8 chars are required"}), 400
    if role not in ("lecturer", "admin"):
        role = "lecturer"
    # First user ever becomes admin; afterwards self-registration is lecturer only.
    if db.users().count_documents({}) == 0:
        role = "admin"
    elif role == "admin":
        role = "lecturer"

    if db.users().find_one({"email": email}):
        return jsonify({"error": "Email already registered"}), 409

    doc = {
        "name": name,
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "active": True,
        "created_at": db.utcnow(),
    }
    res = db.users().insert_one(doc)
    doc["_id"] = res.inserted_id
    token = create_access_token(doc)
    return jsonify({"token": token, "user": jsonify_doc(doc)}), 201


@bp.post("/login")
def login():
    """First factor: validate password, then email a short-lived OTP."""
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = db.users().find_one({"email": email})
    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid credentials"}), 401
    if not user.get("active", True):
        return jsonify({"error": "Account disabled"}), 403

    otp = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = db.utcnow() + timedelta(minutes=config.EMAIL_OTP_TTL_MINUTES)
    db.users().update_one(
        {"_id": user["_id"]},
        {"$set": {
            "login_otp_hash": hashlib.sha256(otp.encode()).hexdigest(),
            "login_otp_expires_at": expires_at,
            "login_otp_attempts": 0,
        }},
    )
    try:
        send_login_otp(user.get("name", "User"), email, otp)
    except Exception:
        db.users().update_one(
            {"_id": user["_id"]},
            {"$unset": {"login_otp_hash": "", "login_otp_expires_at": ""},
             "$set": {"login_otp_attempts": 0}},
        )
        return jsonify({"error": "Could not send verification email. Check SMTP settings in backend/.env."}), 503

    return jsonify({
        "message": "Verification code sent to your email.",
        "requires_otp": True,
        "email": email,
    })


@bp.post("/verify-otp")
def verify_login_otp():
    """Second factor: verify email OTP and only then issue the JWT."""
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    otp = str(data.get("otp") or "").strip()
    if not email or not otp:
        return jsonify({"error": "Email and verification code are required"}), 400

    user = db.users().find_one({"email": email})
    if not user or not user.get("login_otp_hash"):
        return jsonify({"error": "No pending verification. Please sign in again."}), 400
    if user.get("login_otp_attempts", 0) >= 5:
        db.users().update_one({"_id": user["_id"]}, {"$unset": {
            "login_otp_hash": "", "login_otp_expires_at": ""
        }})
        return jsonify({"error": "Too many incorrect attempts. Please sign in again."}), 429
    expires_at = user.get("login_otp_expires_at")
    # PyMongo returns naive UTC datetimes by default; normalize before comparing.
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not expires_at or expires_at <= db.utcnow():
        db.users().update_one({"_id": user["_id"]}, {"$unset": {
            "login_otp_hash": "", "login_otp_expires_at": ""
        }})
        return jsonify({"error": "Verification code expired. Please sign in again."}), 401
    submitted_hash = hashlib.sha256(otp.encode()).hexdigest()
    if not secrets.compare_digest(submitted_hash, user["login_otp_hash"]):
        db.users().update_one({"_id": user["_id"]}, {"$inc": {"login_otp_attempts": 1}})
        return jsonify({"error": "Incorrect verification code"}), 401

    db.users().update_one({"_id": user["_id"]}, {"$unset": {
        "login_otp_hash": "", "login_otp_expires_at": "", "login_otp_attempts": ""
    }})
    token = create_access_token(user)
    g.current_user = user
    log_action("LOGIN")
    return jsonify({"token": token, "user": jsonify_doc(user)})


@bp.post("/logout")
@jwt_required
def logout():
    # Stateless JWT: the client discards the token. We just audit it.
    log_action("LOGOUT")
    return jsonify({"message": "Logged out"})


@bp.get("/me")
@jwt_required
def me():
    return jsonify({"user": jsonify_doc(g.current_user)})
