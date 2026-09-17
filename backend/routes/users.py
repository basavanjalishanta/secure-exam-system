"""Admin user management."""
from bson import ObjectId
from flask import Blueprint, g, jsonify, request

from models import db
from utils.audit import log_action
from utils.security import admin_required, hash_password
from utils.serialization import jsonify_doc

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("")
@admin_required
def list_users():
    users = list(db.users().find().sort("created_at", -1))
    return jsonify({"users": jsonify_doc(users)})


@bp.post("")
@admin_required
def create_user():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role", "lecturer")
    if role not in ("lecturer", "admin"):
        return jsonify({"error": "role must be lecturer or admin"}), 400
    if not name or not email or len(password) < 8:
        return jsonify({"error": "name, email, password(>=8) required"}), 400
    if db.users().find_one({"email": email}):
        return jsonify({"error": "Email already exists"}), 409
    doc = {
        "name": name, "email": email, "password_hash": hash_password(password),
        "role": role, "active": True, "created_at": db.utcnow(),
    }
    res = db.users().insert_one(doc)
    doc["_id"] = res.inserted_id
    log_action("CREATE_USER", target_user=email, role=role)
    return jsonify({"user": jsonify_doc(doc)}), 201


@bp.patch("/<user_id>")
@admin_required
def update_user(user_id):
    data = request.get_json(force=True) or {}
    update = {}
    if "role" in data and data["role"] in ("lecturer", "admin"):
        update["role"] = data["role"]
    if "active" in data:
        update["active"] = bool(data["active"])
    if "password" in data and len(data["password"]) >= 8:
        update["password_hash"] = hash_password(data["password"])
    if not update:
        return jsonify({"error": "nothing to update"}), 400
    db.users().update_one({"_id": ObjectId(user_id)}, {"$set": update})
    log_action("UPDATE_USER", target_user_id=user_id, fields=list(update.keys()))
    return jsonify({"user": jsonify_doc(db.users().find_one({"_id": ObjectId(user_id)}))})


@bp.delete("/<user_id>")
@admin_required
def delete_user(user_id):
    if str(g.current_user["_id"]) == user_id:
        return jsonify({"error": "You cannot delete your own account"}), 400
    db.users().delete_one({"_id": ObjectId(user_id)})
    log_action("DELETE_USER", target_user_id=user_id)
    return jsonify({"message": "deleted"})
