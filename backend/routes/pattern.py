"""Previous-paper pattern analysis + pattern selection."""
from bson import ObjectId
from flask import Blueprint, jsonify, request

from models import db
from services import pattern_service
from utils.audit import log_action
from utils.security import lecturer_required

bp = Blueprint("pattern", __name__, url_prefix="/api/pattern")


@bp.get("/defaults")
@lecturer_required
def defaults():
    return jsonify({"patterns": pattern_service.default_patterns()})


@bp.post("/analyze")
@lecturer_required
def analyze():
    data = request.get_json(force=True) or {}
    subject_id = data.get("subject_id")
    if not subject_id:
        return jsonify({"error": "subject_id required"}), 400
    docs = list(db.documents().find({"subject_id": subject_id, "type": "previous_paper"}))
    if not docs:
        return jsonify({"error": "No previous question papers uploaded for this subject"}), 404

    texts = [d.get("extracted_text", "") for d in docs]
    result = pattern_service.analyze_papers(texts)
    db.subjects().update_one(
        {"_id": ObjectId(subject_id)}, {"$set": {"pattern_analysis": result}}
    )
    log_action("ANALYZE_PATTERN", subject_id=subject_id,
               papers=len(docs), questions=result.get("questions_found"))
    return jsonify({"analysis": result})


@bp.post("/select")
@lecturer_required
def select():
    """Persist the chosen pattern (auto-selected or manual) for a subject."""
    data = request.get_json(force=True) or {}
    subject_id = data.get("subject_id")
    mode = data.get("mode", "auto")  # auto | manual
    subject = db.subjects().find_one({"_id": ObjectId(subject_id)}) if subject_id else None
    if not subject:
        return jsonify({"error": "subject not found"}), 404

    if mode == "manual" and data.get("pattern"):
        pattern = data["pattern"]
    else:
        analysis = subject.get("pattern_analysis") or {}
        pattern = analysis.get("suggested_pattern") or pattern_service.default_patterns()[0]

    pattern.setdefault("total_marks", sum(s["total"] for s in pattern["sections"]))
    db.subjects().update_one(
        {"_id": ObjectId(subject_id)},
        {"$set": {"selected_pattern": pattern, "pattern_mode": mode}},
    )
    log_action("SELECT_PATTERN", subject_id=subject_id, mode=mode,
               total_marks=pattern["total_marks"])
    return jsonify({"pattern": pattern, "mode": mode})
