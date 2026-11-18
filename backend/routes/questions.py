"""AI question generation + asynchronous job tracking + single-question regeneration."""
from bson import ObjectId
from flask import Blueprint, current_app, g, jsonify, request

from models import db
from services import ai_service, generation_worker, pattern_service, rag_service
from utils.audit import log_action
from utils.security import lecturer_required
from utils.serialization import jsonify_doc

bp = Blueprint("questions", __name__, url_prefix="/api/questions")

@bp.get("/latest")
@lecturer_required
def get_latest():
    subject_id = request.args.get("subject_id")
    query = {"subject_id": subject_id} if subject_id else {}
    gen = db.generated_questions().find_one(query, sort=[("_id", -1)])
    if gen and gen.get("questions"):
        return jsonify({"questions": gen["questions"], "pattern": gen.get("pattern")}), 200
    job = db.generation_jobs().find_one(query, sort=[("_id", -1)])
    if job and job.get("questions"):
        return jsonify({"questions": job["questions"], "pattern": job.get("pattern")}), 200
    return jsonify({"questions": []}), 200

CTX_PREVIEW = 700
_LLM_CTX_CHARS = 1400


def _subject_or_404(subject_id):
    return db.subjects().find_one({"_id": ObjectId(subject_id)}) if subject_id else None


def _previous_questions(subject_id: str) -> list[str]:
    out = []
    for d in db.documents().find({"subject_id": subject_id, "type": "previous_paper"}):
        for line in (d.get("extracted_text") or "").splitlines():
            line = line.strip()
            if len(line) > 25 and any(v in line.lower() for v in ("explain", "define", "what", "describe", "discuss", "write")):
                out.append(line)
    for q in db.question_bank().find({"subject_id": subject_id}, {"question": 1}):
        out.append(q["question"])
    return out[:30]


def _generate_for_slot(subject, slot, previous, accepted_texts):
    query = f"Unit {slot['unit']} {slot.get('topic_hint', '')} {slot['question_type']} key concepts"
    passages = rag_service.retrieve(str(subject["_id"]), query, unit=slot["unit"], top_k=3)
    context = rag_service.build_context(passages, max_chars=_LLM_CTX_CHARS)
    cand = generation_worker.generate_unique_question(
        subject=subject,
        slot=slot,
        context=context,
        previous_questions=list(previous) + list(accepted_texts),
    )
    if not cand:
        return None
    cand.update({
        "section": slot["section"],
        "source": [f"{p['doc_type']} (unit {p['unit']}, score {p['score']})" for p in passages],
        "source_context": context[:CTX_PREVIEW],
    })
    return cand


@bp.post("/generate")
@lecturer_required
def generate():
    """Initiates an asynchronous question generation job and returns immediately."""
    data = request.get_json(force=True) or {}
    subject = _subject_or_404(data.get("subject_id"))
    if not subject:
        return jsonify({"error": "subject not found"}), 404

    pattern = data.get("pattern") or subject.get("selected_pattern")
    if not pattern:
        return jsonify({"error": "No pattern selected. Run pattern selection first."}), 400
    pattern = pattern_service.normalize_pattern(pattern)

    units = data.get("units")
    if not units:
        available_units = [u["unit"] for u in subject.get("units", [])] or [1, 2, 3, 4, 5]
        units = available_units[:pattern.get("units", len(available_units))]
    analysis = subject.get("pattern_analysis") or {}
    unit_weights = data.get("unit_weights") or {
        k: v / 100.0 for k, v in analysis.get("unit_distribution_percent", {}).items()
    } or None
    topic_hints = data.get("topic_hints") or {}
    if not isinstance(topic_hints, dict) or any(
        not isinstance(value, str) or len(value) > 500 for value in topic_hints.values()
    ):
        return jsonify({"error": "topic_hints must map unit numbers to topic text (maximum 500 characters per unit)"}), 400

    try:
        job_id = generation_worker.create_generation_job(
            subject_id=str(subject["_id"]),
            pattern=pattern,
            units=units,
            unit_weights=unit_weights,
            topic_hints=topic_hints,
            difficulty=data.get("difficulty", ""),
            bloom_level=data.get("bloom_level", ""),
            user_id=str(g.current_user["_id"]),
        )
        log_action("CREATE_GENERATION_JOB", subject_id=str(subject["_id"]), job_id=job_id)
        return jsonify({
            "job_id": job_id,
            "status": "queued",
            "message": "Question generation job successfully started.",
            "pattern": pattern,
        }), 202
    except Exception as exc:
        current_app.logger.exception("Failed to start generation job: %s", exc)
        if isinstance(exc, ValueError):
            return jsonify({"error": str(exc)}), 400
        return jsonify({"error": f"Failed to start generation job: {exc}"}), 500


@bp.get("/jobs/<job_id>")
@lecturer_required
def get_job_progress(job_id):
    """Returns real-time progress, completed questions, and current stage of a generation job."""
    job = db.generation_jobs().find_one({"job_id": job_id})
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"job": jsonify_doc(job)}), 200


@bp.post("/jobs/<job_id>/regenerate-slot")
@lecturer_required
def regenerate_slot(job_id):
    """Regenerates a single specific question slot independently."""
    data = request.get_json(force=True) or {}
    slot_index = data.get("slot_index")
    if slot_index is None:
        return jsonify({"error": "slot_index is required"}), 400

    try:
        new_q = generation_worker.regenerate_single_slot(job_id, int(slot_index))
        if not new_q:
            return jsonify({"error": "Could not regenerate question for slot"}), 502
        return jsonify({"question": new_q}), 200
    except ai_service.AIProviderError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@bp.post("/regenerate")
@lecturer_required
def regenerate():
    """Synchronous single question replacement used from the Question Review screen."""
    data = request.get_json(force=True) or {}
    subject = _subject_or_404(data.get("subject_id"))
    if not subject:
        return jsonify({"error": "subject not found"}), 404

    q = data.get("question") or {}
    slot = {
        "section": q.get("section", "B"),
        "unit": int(q.get("unit", 1)),
        "marks": int(q.get("marks", 6)),
        "difficulty": q.get("difficulty", "Medium"),
        "bloom_level": q.get("bloom_level", "Understand"),
        "question_type": q.get("question_type", "Theory"),
        "topic_hint": data.get("topic_hint", q.get("topic", "")),
    }

    avoid = data.get("existing_questions", [])
    if not isinstance(avoid, list):
        avoid = []
    avoid = [question for question in avoid if isinstance(question, str)]
    avoid.extend(_previous_questions(str(subject["_id"])))
    if q.get("question"):
        avoid.append(q["question"])

    try:
        new_q = _generate_for_slot(subject, slot, avoid, [])
    except ai_service.AIProviderError as exc:
        return jsonify({"error": str(exc)}), 503
    if not new_q:
        return jsonify({"error": "could not generate a replacement question"}), 502

    new_q["index"] = q.get("index")
    new_q["section"] = slot["section"]

    log_action("REGENERATE_QUESTION", subject_id=str(subject["_id"]), unit=slot["unit"])
    return jsonify({"question": new_q})
