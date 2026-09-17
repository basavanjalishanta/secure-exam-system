"""Subject management."""
from bson import ObjectId
from flask import Blueprint, g, jsonify, request

from models import db
from utils.audit import log_action
from utils.security import admin_required, lecturer_required
from utils.serialization import jsonify_doc

bp = Blueprint("subjects", __name__, url_prefix="/api/subjects")


@bp.get("")
@lecturer_required
def list_subjects():
    subjects = list(db.subjects().find().sort("name", 1))
    return jsonify({"subjects": jsonify_doc(subjects)})


@bp.get("/<subject_id>")
@lecturer_required
def get_subject(subject_id):
    s = db.subjects().find_one({"_id": ObjectId(subject_id)})
    if not s:
        return jsonify({"error": "not found"}), 404
    counts = {
        "documents": db.documents().count_documents({"subject_id": subject_id}),
        "questions": db.question_bank().count_documents({"subject_id": subject_id}),
        "papers": db.question_papers().count_documents({"subject_id": subject_id}),
    }
    out = jsonify_doc(s)
    out["counts"] = counts
    return jsonify({"subject": out})


@bp.post("")
@lecturer_required
def create_subject():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip().upper()
    if not name or not code:
        return jsonify({"error": "name and code required"}), 400
    if db.subjects().find_one({"code": code}):
        return jsonify({"error": "Subject code already exists"}), 409
    units = []
    for u in data.get("units", []):
        if isinstance(u, dict):
            units.append({"unit": int(u.get("unit")), "title": u.get("title", "")})
        else:
            units.append({"unit": int(u), "title": ""})
    doc = {
        "name": name,
        "code": code,
        "semester": int(data.get("semester", 1)),
        "units": units or [{"unit": i, "title": ""} for i in range(1, 6)],
        "created_by": str(g.current_user["_id"]),
        "created_at": db.utcnow(),
    }
    res = db.subjects().insert_one(doc)
    doc["_id"] = res.inserted_id
    log_action("CREATE_SUBJECT", subject_code=code)
    return jsonify({"subject": jsonify_doc(doc)}), 201


@bp.patch("/<subject_id>")
@lecturer_required
def update_subject(subject_id):
    data = request.get_json(force=True) or {}
    update = {}
    for f in ("name", "semester"):
        if f in data:
            update[f] = data[f]
    if "units" in data:
        update["units"] = [
            {"unit": int(u.get("unit")), "title": u.get("title", "")} if isinstance(u, dict)
            else {"unit": int(u), "title": ""}
            for u in data["units"]
        ]
    db.subjects().update_one({"_id": ObjectId(subject_id)}, {"$set": update})
    return jsonify({"subject": jsonify_doc(db.subjects().find_one({"_id": ObjectId(subject_id)}))})


@bp.delete("/<subject_id>")
@admin_required
def delete_subject(subject_id):
    db.subjects().delete_one({"_id": ObjectId(subject_id)})
    db.documents().delete_many({"subject_id": subject_id})
    db.chunks().delete_many({"subject_id": subject_id})
    log_action("DELETE_SUBJECT", subject_id=subject_id)
    return jsonify({"message": "deleted"})
