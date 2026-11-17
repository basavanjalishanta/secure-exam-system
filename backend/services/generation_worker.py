"""Background generation worker for examination question papers.

Ensures question generation runs asynchronously without blocking HTTP requests:
- Generates questions one-by-one with deterministic blueprint slot mapping.
- Bounded retries (max 2 attempts) per slot.
- Saves every generated question immediately (incremental persistence).
- Fault-tolerant: preserves successful questions even if later slots fail.
- Live stage, progress, and error tracking in MongoDB.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any
from bson import ObjectId

from config import config
from models import db
from services import ai_service, pattern_service, rag_service
from utils.audit import log_action

logger = logging.getLogger(__name__)

_WORKER_LOCK = threading.Lock()
_ACTIVE_JOBS: set[str] = set()


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


def create_generation_job(*, subject_id: str, pattern: dict, units: list[int],
                          unit_weights: dict | None = None, difficulty: str = "",
                          bloom_level: str = "", user_id: str) -> str:
    """Creates a new queued generation job record and launches the background worker."""
    subject = db.subjects().find_one({"_id": ObjectId(subject_id)})
    if not subject:
        raise ValueError("Subject not found")

    plan = pattern_service.build_generation_plan(pattern, units, unit_weights)
    if difficulty:
        for s in plan:
            s["difficulty"] = difficulty
    if bloom_level:
        for s in plan:
            s["bloom_level"] = bloom_level

    job_id = str(uuid.uuid4())
    job_doc = {
        "job_id": job_id,
        "subject_id": subject_id,
        "subject_name": subject.get("name"),
        "pattern": pattern,
        "units": units,
        "total_slots": len(plan),
        "completed_count": 0,
        "failed_count": 0,
        "status": "queued",
        "current_stage": "Job queued for generation...",
        "plan": plan,
        "questions": [],
        "errors": [],
        "created_by": user_id,
        "created_at": db.utcnow(),
        "updated_at": db.utcnow(),
    }
    db.generation_jobs().insert_one(job_doc)

    # Launch background thread
    t = threading.Thread(target=_process_job, args=(job_id,), daemon=True)
    t.start()
    return job_id


def _process_job(job_id: str):
    with _WORKER_LOCK:
        if job_id in _ACTIVE_JOBS:
            return
        _ACTIVE_JOBS.add(job_id)

    try:
        job = db.generation_jobs().find_one({"job_id": job_id})
        if not job or job.get("status") in ("completed", "canceled"):
            return

        db.generation_jobs().update_one(
            {"job_id": job_id},
            {"$set": {"status": "in_progress", "current_stage": "Initializing RAG context...", "updated_at": db.utcnow()}}
        )

        subject_id = job["subject_id"]
        subject = db.subjects().find_one({"_id": ObjectId(subject_id)})
        plan = job["plan"]
        previous = _previous_questions(subject_id)

        accepted_questions = []

        for idx, slot in enumerate(plan):
            stage_text = (
                f"Generating Section {slot['section']} Question {idx + 1} of {len(plan)} "
                f"(Unit {slot['unit']}, {slot['marks']} marks, {slot['difficulty']})..."
            )
            db.generation_jobs().update_one(
                {"job_id": job_id},
                {"$set": {"current_stage": stage_text, "updated_at": db.utcnow()}}
            )

            # Retrieve RAG context for this slot
            query = f"Unit {slot['unit']} {slot.get('topic_hint', '')} {slot['question_type']} key concepts and definitions"
            passages = rag_service.retrieve(
                subject_id, query, unit=slot["unit"],
                doc_types=["syllabus", "textbook", "notes"],
                top_k=3,
            )
            context = rag_service.build_context(passages, max_chars=1400)
            sources = [f"{p['doc_type']} (unit {p['unit']}, score {p['score']})" for p in passages]

            # Generate with up to 2 attempts
            cand = None
            slot_error = None

            for attempt in range(1, 3):
                try:
                    candidates = ai_service.generate_questions(
                        subject=subject,
                        unit=slot["unit"],
                        topic_hint=slot.get("topic_hint", ""),
                        count=1,
                        marks=slot["marks"],
                        difficulty=slot["difficulty"],
                        bloom=slot["bloom_level"],
                        qtype=slot["question_type"],
                        context=context,
                        previous_questions=previous[:10],
                    )
                    if candidates and len(candidates[0].get("question", "")) > 10:
                        cand = candidates[0]
                        break
                except Exception as exc:
                    slot_error = str(exc)
                    logger.warning("Job %s slot %d attempt %d failed: %s", job_id, idx, attempt, exc)

            if not cand:
                # Slot failed after attempts: log error and create placeholder so paper structure is preserved
                db.generation_jobs().update_one(
                    {"job_id": job_id},
                    {
                        "$inc": {"failed_count": 1},
                        "$push": {
                            "errors": f"Slot {idx + 1} (Sec {slot['section']}) failed: {slot_error or 'invalid question format'}"
                        },
                        "$set": {"updated_at": db.utcnow()}
                    }
                )
                continue

            # Check semantic duplicate
            is_dup, score, matched = rag_service.is_duplicate(
                subject_id, cand["question"], extra_pool=[q["question"] for q in accepted_questions] + previous
            )

            cand.update({
                "index": idx,
                "section": slot["section"],
                "unit": slot["unit"],
                "marks": slot["marks"],
                "full_question_num": slot.get("full_question_num"),
                "sub_part": slot.get("sub_part"),
                "is_or": slot.get("is_or", False),
                "source": sources,
                "source_context": context[:500],
                "similarity_score": score,
                "duplicate": is_dup,
                "matched_question": matched if is_dup else None,
                "status": "accepted",
            })

            accepted_questions.append(cand)

            # Persist question immediately
            db.generation_jobs().update_one(
                {"job_id": job_id},
                {
                    "$push": {"questions": cand},
                    "$inc": {"completed_count": 1},
                    "$set": {"updated_at": db.utcnow()}
                }
            )

            # Brief pause between questions to stay within Groq TPM limits.
            # Groq free tier: 8000 tokens/min; each question uses ~1200 tokens
            # => ~6 questions/min max => 10s gap per question is safe.
            provider_name = (config.AI_PROVIDER or "").lower()
            if provider_name in ("groq", "grok", "cloud"):
                time.sleep(10)

        # Finalize job
        final_status = "completed" if len(accepted_questions) == len(plan) else "completed_with_errors"
        db.generation_jobs().update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": final_status,
                    "current_stage": "Question paper generation completed successfully.",
                    "updated_at": db.utcnow()
                }
            }
        )

        # Store in generated_questions collection for compatibility with review workflow
        db.generated_questions().insert_one({
            "generation_id": job_id,
            "subject_id": subject_id,
            "pattern": job["pattern"],
            "questions": accepted_questions,
            "created_by": job["created_by"],
            "created_at": db.utcnow(),
        })

        log_action("GENERATE_QUESTIONS_JOB_COMPLETED", job_id=job_id, subject_id=subject_id, count=len(accepted_questions))

    except Exception as exc:
        logger.exception("Job %s crashed: %s", job_id, exc)
        db.generation_jobs().update_one(
            {"job_id": job_id},
            {"$set": {"status": "failed", "current_stage": f"Error: {exc}", "updated_at": db.utcnow()}}
        )
    finally:
        with _WORKER_LOCK:
            _ACTIVE_JOBS.discard(job_id)


def regenerate_single_slot(job_id: str, slot_index: int) -> dict | None:
    """Regenerates a single specific question slot independently."""
    job = db.generation_jobs().find_one({"job_id": job_id})
    if not job:
        raise ValueError("Job not found")

    plan = job.get("plan", [])
    if slot_index < 0 or slot_index >= len(plan):
        raise ValueError("Invalid slot index")

    slot = plan[slot_index]
    subject_id = job["subject_id"]
    subject = db.subjects().find_one({"_id": ObjectId(subject_id)})
    previous = _previous_questions(subject_id)

    query = f"Unit {slot['unit']} {slot.get('topic_hint', '')} {slot['question_type']} key concepts"
    passages = rag_service.retrieve(subject_id, query, unit=slot["unit"], top_k=3)
    context = rag_service.build_context(passages, max_chars=1400)

    cand = None
    for _ in range(2):
        candidates = ai_service.generate_questions(
            subject=subject,
            unit=slot["unit"],
            topic_hint=slot.get("topic_hint", ""),
            count=1,
            marks=slot["marks"],
            difficulty=slot["difficulty"],
            bloom=slot["bloom_level"],
            qtype=slot["question_type"],
            context=context,
            previous_questions=previous[:10],
        )
        if candidates:
            cand = candidates[0]
            break

    if not cand:
        return None

    cand.update({
        "index": slot_index,
        "section": slot["section"],
        "unit": slot["unit"],
        "marks": slot["marks"],
        "full_question_num": slot.get("full_question_num"),
        "sub_part": slot.get("sub_part"),
        "is_or": slot.get("is_or", False),
        "source": [f"{p['doc_type']} (unit {p['unit']}, score {p['score']})" for p in passages],
        "source_context": context[:500],
        "similarity_score": 0.0,
        "duplicate": False,
        "status": "accepted",
    })

    # Update in questions array inside generation_jobs
    db.generation_jobs().update_one(
        {"job_id": job_id, "questions.index": slot_index},
        {"$set": {"questions.$": cand, "updated_at": db.utcnow()}}
    )
    return cand
