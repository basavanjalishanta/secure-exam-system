"""Question bank CRUD."""
from bson import ObjectId
from flask import Blueprint, jsonify, request

from models import db
from services import rag_service
from utils.audit import log_action
from utils.security import lecturer_required
from utils.serialization import jsonify_doc

bp = Blueprint("question_bank", __name__, url_prefix="/api/question-bank")


@bp.get("")
@lecturer_required
def list_questions():
    q = {}
    if request.args.get("subject_id"):
        q["subject_id"] = request.args["subject_id"]
    if request.args.get("unit"):
        q["unit"] = int(request.args["unit"])
    if request.args.get("difficulty"):
        q["difficulty"] = request.args["difficulty"]
    if request.args.get("search"):
        q["$text"] = {"$search": request.args["search"]}
    rows = list(db.question_bank().find(q).sort("created_at", -1).limit(500))
    return jsonify({"questions": jsonify_doc(rows), "count": len(rows)})


@bp.post("")
@lecturer_required
def add_question():
    data = request.get_json(force=True) or {}
    text = (data.get("question") or "").strip()
    if not text or not data.get("subject_id"):
        return jsonify({"error": "subject_id and question required"}), 400
    is_dup, score, matched = rag_service.is_duplicate(data["subject_id"], text)
    if is_dup:
        return jsonify({"error": "Near-duplicate of an existing question",
                        "similarity_score": score, "matched": matched}), 409
    doc = {
        "subject_id": data["subject_id"],
        "unit": data.get("unit"),
        "topic": data.get("topic"),
        "question": text,
        "answer": data.get("answer", ""),
        "marks": data.get("marks"),
        "difficulty": data.get("difficulty", "Medium"),
        "bloom_level": data.get("bloom_level", "Understand"),
        "question_type": data.get("question_type", "Theory"),
        "source": data.get("source", ["manual"]),
        "embedding": rag_service.embed_text(text),
        "usage_count": 0,
        "created_at": db.utcnow(),
    }
    res = db.question_bank().insert_one(doc)
    doc["_id"] = res.inserted_id
    log_action("ADD_QUESTION_BANK", subject_id=data["subject_id"])
    return jsonify({"question": jsonify_doc(doc)}), 201


@bp.delete("/<question_id>")
@lecturer_required
def delete_question(question_id):
    db.question_bank().delete_one({"_id": ObjectId(question_id)})
    log_action("DELETE_QUESTION_BANK", question_id=question_id)
    return jsonify({"message": "deleted"})
