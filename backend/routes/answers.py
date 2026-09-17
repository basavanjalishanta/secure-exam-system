"""Answer-key generation (RAG, depth scaled by marks)."""
from bson import ObjectId
from flask import Blueprint, jsonify, request

from models import db
from services import ai_service, rag_service
from utils.audit import log_action
from utils.security import lecturer_required

bp = Blueprint("answers", __name__, url_prefix="/api/answers")


@bp.post("/generate")
@lecturer_required
def generate_answers():
    data = request.get_json(force=True) or {}
    subject = db.subjects().find_one({"_id": ObjectId(data["subject_id"])}) if data.get("subject_id") else None
    if not subject:
        return jsonify({"error": "subject not found"}), 404
    questions = data.get("questions") or []
    if not questions:
        return jsonify({"error": "questions required"}), 400

    out = []
    for q in questions:
        passages = rag_service.retrieve(
            str(subject["_id"]),
            f"{q.get('topic', '')} {q.get('question', '')}",
            unit=q.get("unit"),
            doc_types=["textbook", "notes", "syllabus"],
        )
        context = rag_service.build_context(passages)
        answer = ai_service.generate_answer(question=q, context=context)
        support = rag_service.hallucination_score(answer, context)
        enriched = dict(q)
        enriched["answer"] = answer
        enriched["answer_support"] = support
        enriched["answer_sources"] = [f"{p['doc_type']} unit {p['unit']}" for p in passages]
        out.append(enriched)

    log_action("GENERATE_ANSWERS", subject_id=str(subject["_id"]), count=len(out))
    return jsonify({"questions": out})
