"""Answer-key generation (RAG, depth scaled by marks)."""
from bson import ObjectId
from bson.errors import InvalidId
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
    subject_id = data.get("subject_id")
    if not isinstance(subject_id, str) or not ObjectId.is_valid(subject_id):
        return jsonify({"error": "A valid subject_id is required"}), 400
    try:
        subject = db.subjects().find_one({"_id": ObjectId(subject_id)})
    except InvalidId:
        return jsonify({"error": "A valid subject_id is required"}), 400
    if not subject:
        return jsonify({"error": "subject not found"}), 404
    questions = data.get("questions") or []
    if not isinstance(questions, list) or not questions:
        return jsonify({"error": "questions must be a non-empty list"}), 400
    if any(
        not isinstance(question, dict)
        or not isinstance(question.get("question"), str)
        or not question["question"].strip()
        for question in questions
    ):
        return jsonify({"error": "Each question must include non-empty question text"}), 400

    out = []
    try:
        for q in questions:
            passages = rag_service.retrieve(
                str(subject["_id"]),
                f"{q.get('topic', '')} {q.get('question', '')}",
                unit=q.get("unit"),
                doc_types=["textbook", "notes", "syllabus"],
            )
            context = rag_service.build_context(passages)
            if not context.strip():
                question_index = q.get("index")
                if not isinstance(question_index, int) or isinstance(question_index, bool):
                    question_index = len(out)
                return jsonify({
                    "error": (
                        f"No course material was retrieved for question {question_index + 1}. "
                        "Upload syllabus or notes for this subject before generating its answer."
                    )
                }), 422
            answer = ai_service.generate_answer(question=q, context=context)
            support = rag_service.hallucination_score(answer, context)
            enriched = dict(q)
            enriched["answer"] = answer
            enriched["answer_support"] = support
            enriched["answer_sources"] = [f"{p['doc_type']} unit {p['unit']}" for p in passages]
            out.append(enriched)
    except ai_service.AIProviderError as exc:
        return jsonify({"error": str(exc)}), 503

    log_action("GENERATE_ANSWERS", subject_id=str(subject["_id"]), count=len(out))
    return jsonify({"questions": out})
