"""Validation engine endpoint + automatic fix."""
from bson import ObjectId
from flask import Blueprint, jsonify, request

from models import db
from routes.questions import _generate_for_slot, _previous_questions
from services import validation_service
from utils.audit import log_action
from utils.security import lecturer_required

bp = Blueprint("validation", __name__, url_prefix="/api/validation")


def _subject(subject_id):
    return db.subjects().find_one({"_id": ObjectId(subject_id)}) if subject_id else None


@bp.post("/validate")
@lecturer_required
def validate():
    data = request.get_json(force=True) or {}
    subject = _subject(data.get("subject_id"))
    if not subject:
        return jsonify({"error": "subject not found"}), 404
    pattern = data.get("pattern") or subject.get("selected_pattern")
    questions = data.get("questions") or []
    context_by_index = {
        i: q.get("source_context", "") for i, q in enumerate(questions) if q.get("source_context")
    }
    result = validation_service.validate_paper(
        subject=subject, pattern=pattern, questions=questions,
        context_by_index=context_by_index,
    )
    log_action("VALIDATE_PAPER", subject_id=str(subject["_id"]),
               valid=result["valid"], errors=len(result["errors"]))
    return jsonify({"validation": result})


@bp.post("/fix")
@lecturer_required
def auto_fix():
    """Regenerate the questions flagged by validation (duplicate / weak support / bad format)."""
    data = request.get_json(force=True) or {}
    subject = _subject(data.get("subject_id"))
    if not subject:
        return jsonify({"error": "subject not found"}), 404
    questions = data.get("questions") or []
    pattern = data.get("pattern") or subject.get("selected_pattern")

    validation = validation_service.validate_paper(
        subject=subject, pattern=pattern, questions=questions,
        context_by_index={i: q.get("source_context", "") for i, q in enumerate(questions)},
    )
    bad_indexes = sorted({e["question_index"] for e in validation["errors"] if "question_index" in e})
    previous = _previous_questions(str(subject["_id"]))
    accepted = [q["question"] for i, q in enumerate(questions) if i not in bad_indexes]

    fixed = list(questions)
    for idx in bad_indexes:
        old = questions[idx]
        slot = {
            "section": old.get("section", "B"),
            "unit": int(old.get("unit", 1)),
            "marks": int(old.get("marks", 6)),
            "difficulty": old.get("difficulty", "Medium"),
            "bloom_level": old.get("bloom_level", "Understand"),
            "question_type": old.get("question_type", "Theory"),
            "topic_hint": old.get("topic", ""),
        }
        new_q = _generate_for_slot(subject, slot, previous, accepted)
        if new_q:
            new_q["index"] = idx
            fixed[idx] = new_q
            accepted.append(new_q["question"])

    revalidation = validation_service.validate_paper(
        subject=subject, pattern=pattern, questions=fixed,
        context_by_index={i: q.get("source_context", "") for i, q in enumerate(fixed)},
    )
    log_action("AUTOFIX_PAPER", subject_id=str(subject["_id"]),
               fixed=len(bad_indexes), now_valid=revalidation["valid"])
    return jsonify({"questions": fixed, "fixed_indexes": bad_indexes, "validation": revalidation})
