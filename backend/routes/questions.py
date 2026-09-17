"""AI question generation + single-question regeneration (RAG pipeline)."""
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from bson import ObjectId
from flask import Blueprint, g, jsonify, request

from config import config
from models import db
from services import ai_service, pattern_service, rag_service
from utils.audit import log_action
from utils.security import lecturer_required

bp = Blueprint("questions", __name__, url_prefix="/api/questions")

CTX_PREVIEW = 700


def _subject_or_404(subject_id):
    return db.subjects().find_one({"_id": ObjectId(subject_id)}) if subject_id else None


def _previous_questions(subject_id: str) -> list[str]:
    out = []
    for d in db.documents().find({"subject_id": subject_id, "type": "previous_paper"}):
        for line in (d.get("extracted_text") or "").splitlines():
            line = line.strip()
            if len(line) > 25 and any(v in line.lower() for v in
                                      ("explain", "define", "what", "describe", "discuss", "write")):
                out.append(line)
    for q in db.question_bank().find({"subject_id": subject_id}, {"question": 1}):
        out.append(q["question"])
    return out[:60]


def _generate_for_slot(subject, slot, previous, accepted_texts):
    query = f"Unit {slot['unit']} {slot.get('topic_hint', '')} " \
            f"{slot['question_type']} {slot['difficulty']} concepts and definitions"
    passages = rag_service.retrieve(
        str(subject["_id"]), query, unit=slot["unit"],
        doc_types=["syllabus", "textbook", "notes"],
    )
    context = rag_service.build_context(passages)
    # Over-generating extra candidates is cheap for the template-based mock
    # provider but multiplies wall-clock time for a real local LLM call, so
    # only over-generate for the mock; a real duplicate from the LLM gets
    # caught by validation and can be regenerated from there.
    over_generate = 1 if config.AI_PROVIDER == "llama" else 3
    generated = ai_service.generate_questions(
        subject=subject,
        unit=slot["unit"],
        topic_hint=slot.get("topic_hint", ""),
        count=over_generate,
        marks=slot["marks"],
        difficulty=slot["difficulty"],
        bloom=slot["bloom_level"],
        qtype=slot["question_type"],
        context=context,
        previous_questions=previous,
    )
    for cand in generated:
        is_dup, score, matched = rag_service.is_duplicate(
            str(subject["_id"]), cand["question"], extra_pool=list(accepted_texts) + previous
        )
        cand.update(
            {
                "section": slot["section"],
                "source": [f"{p['doc_type']} (unit {p['unit']}, score {p['score']})" for p in passages],
                "source_context": context[:CTX_PREVIEW],
                "similarity_score": score,
                "duplicate": is_dup,
                "matched_question": matched if is_dup else None,
            }
        )
        if not is_dup:
            return cand
    # everything was a near-duplicate; return the least-similar candidate flagged
    generated.sort(key=lambda c: c.get("similarity_score", 1))
    return generated[0] if generated else None


@bp.post("/generate")
@lecturer_required
def generate():
    data = request.get_json(force=True) or {}
    subject = _subject_or_404(data.get("subject_id"))
    if not subject:
        return jsonify({"error": "subject not found"}), 404

    pattern = data.get("pattern") or subject.get("selected_pattern")
    if not pattern:
        return jsonify({"error": "No pattern selected. Run pattern selection first."}), 400

    units = data.get("units") or [u["unit"] for u in subject.get("units", [])] or [1, 2, 3, 4, 5]
    analysis = subject.get("pattern_analysis") or {}
    unit_weights = data.get("unit_weights") or {
        k: v / 100.0 for k, v in analysis.get("unit_distribution_percent", {}).items()
    } or None

    plan = pattern_service.build_generation_plan(pattern, units, unit_weights)

    # optional per-request overrides
    if data.get("difficulty"):
        for s in plan:
            s["difficulty"] = data["difficulty"]
    if data.get("bloom_level"):
        for s in plan:
            s["bloom_level"] = data["bloom_level"]

    previous = _previous_questions(str(subject["_id"]))
    questions = []

    if ai_service.get_provider().name == "llama" and len(plan) > 1:
        # A real local LLM can genuinely process several requests concurrently
        # (verified: Ollama overlaps calls rather than fully serializing them),
        # so run slots in parallel instead of one at a time. This sacrifices
        # in-batch incremental duplicate avoidance (each slot only checks
        # against `previous`, not against slots generated earlier in this
        # same batch) - the validation step's "Fix Automatically" catches and
        # regenerates any same-batch near-duplicates that slip through.
        results: list[dict | None] = [None] * len(plan)
        with ThreadPoolExecutor(max_workers=config.LLM_CONCURRENCY) as executor:
            futures = {
                executor.submit(_generate_for_slot, subject, slot, previous, []): i
                for i, slot in enumerate(plan)
            }
            for future in as_completed(futures):
                i = futures[future]
                try:
                    results[i] = future.result()
                except Exception:  # noqa: BLE001 - one bad slot shouldn't fail the batch
                    results[i] = None
        for i, q in enumerate(results):
            if not q:
                continue
            q["index"] = i
            questions.append(q)
    else:
        accepted_texts: list[str] = []
        for i, slot in enumerate(plan):
            q = _generate_for_slot(subject, slot, previous, accepted_texts)
            if not q:
                continue
            q["index"] = i
            accepted_texts.append(q["question"])
            questions.append(q)

    generation_id = str(uuid.uuid4())
    db.generated_questions().insert_one(
        {
            "generation_id": generation_id,
            "subject_id": str(subject["_id"]),
            "pattern": pattern,
            "questions": questions,
            "created_by": str(g.current_user["_id"]),
            "created_at": db.utcnow(),
        }
    )
    log_action("GENERATE_QUESTIONS", subject_id=str(subject["_id"]),
               generation_id=generation_id, count=len(questions),
               provider=ai_service.get_provider().name)
    return jsonify(
        {
            "generation_id": generation_id,
            "pattern": pattern,
            "questions": questions,
            "provider": ai_service.get_provider().name,
        }
    )


@bp.post("/regenerate")
@lecturer_required
def regenerate():
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
    previous = _previous_questions(str(subject["_id"]))
    avoid = data.get("existing_questions", [])
    if q.get("question"):
        avoid = avoid + [q["question"]]
    new_q = _generate_for_slot(subject, slot, previous, avoid)
    if not new_q:
        return jsonify({"error": "could not generate a replacement question"}), 502
    new_q["index"] = q.get("index")
    log_action("REGENERATE_QUESTION", subject_id=str(subject["_id"]), unit=slot["unit"])
    return jsonify({"question": new_q})
