"""Authentication: register, login, logout, me."""
from flask import Blueprint, g, jsonify, request

from models import db
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
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = db.users().find_one({"email": email})
    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid credentials"}), 401
    if not user.get("active", True):
        return jsonify({"error": "Account disabled"}), 403
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
