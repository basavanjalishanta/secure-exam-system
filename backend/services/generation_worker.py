"""Background generation worker for examination question papers.

Ensures question generation runs asynchronously without blocking HTTP requests:
- Generates questions one-by-one with deterministic blueprint slot mapping.
- Bounded retries per slot; semantic duplicates are rejected before persistence.
- Saves every generated question immediately (incremental persistence).
- Fault-tolerant: preserves successful questions even if later slots fail.
- Live stage, progress, and error tracking in MongoDB.
"""
from __future__ import annotations

import logging
import re
import threading
import uuid
from typing import Any
from bson import ObjectId

from models import db
from services import ai_service, pattern_service, rag_service
from utils.audit import log_action

logger = logging.getLogger(__name__)

_WORKER_LOCK = threading.Lock()
_ACTIVE_JOBS: set[str] = set()


def _slot_topic_hint(subject: dict, slot: dict, context: str = "") -> str:
    hint = slot.get("topic_hint")
    if isinstance(hint, str) and hint.strip():
        return hint.strip()

    unit_title = None
    for unit in subject.get("units") or []:
        if isinstance(unit, dict) and str(unit.get("unit")) == str(slot["unit"]):
            title = unit.get("title")
            if isinstance(title, str) and title.strip():
                unit_title = title.strip()
                if not re.fullmatch(r"(?:unit|module)\s*[- ]?\s*\d+", unit_title, re.IGNORECASE):
                    return unit_title
                break

    heading = re.compile(
        rf"^\s*(?:unit|module)\s*[-:]?\s*{re.escape(str(slot['unit']))}\s*[:\-]\s*(.+?)\s*$",
        re.IGNORECASE,
    )
    for line in context.splitlines():
        match = heading.match(line)
        if match:
            title = re.split(r"\s+(?:outline|contents)\s*:", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
            if title.strip():
                return title.strip()[:120]

    if unit_title:
        return unit_title
    return f"Unit {slot['unit']}"


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


def _assign_topic_hints(plan: list[dict], topic_hints: dict | None) -> None:
    topics_by_unit = {}
    for raw_unit, raw_topics in (topic_hints or {}).items():
        try:
            unit_number = int(raw_unit)
        except (TypeError, ValueError):
            continue
        topics = raw_topics if isinstance(raw_topics, list) else re.split(r"[,;\n]+", str(raw_topics))
        clean_topics = [topic.strip() for topic in topics if isinstance(topic, str) and topic.strip()]
        if clean_topics:
            topics_by_unit[unit_number] = clean_topics

    topic_offsets: dict[int, int] = {}
    for slot in plan:
        unit_number = int(slot["unit"])
        topics = topics_by_unit.get(unit_number)
        if topics:
            offset = topic_offsets.get(unit_number, 0)
            slot["topic_hint"] = topics[offset % len(topics)]
            topic_offsets[unit_number] = offset + 1


def _extract_topic_candidates(context: str) -> list[str]:
    text = context.replace("\uf0a7", "|").replace("\u2022", "|").replace("\ufffd", "|")
    candidates = []
    seen = set()
    markers = list(re.finditer(r"\boutline\s*:\s*", text, re.IGNORECASE))
    sentence_words = {"is", "are", "was", "were", "an", "the", "this", "that", "which", "can"}

    def add_candidate(raw: str) -> None:
        value = re.sub(r"\s+", " ", raw).strip(" \t\r\n:.-|")
        value = re.sub(r"\s+Outline\s*:.*$", "", value, flags=re.IGNORECASE).strip(" \t\r\n:.-|")
        words = value.split()
        while words and words[-1].casefold() in {
            "definition", "example", "examples", "outline", "syntax", "where", "note",
        }:
            words.pop()
        value = " ".join(words)
        if (
            not value
            or len(value) > 80
            or len(words) > 6
            or any(word.casefold() in sentence_words for word in words)
            or value.casefold() in {
                "definition", "syntax", "example", "examples", "outline", "unit", "module", "chapter",
            }
            or value.casefold().startswith(("unit ", "module ", "chapter "))
        ):
            return
        key = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
        if key and key not in seen:
            seen.add(key)
            candidates.append(value)

    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        items = re.split(r"\|+", text[marker.end():end])
        for item_index, item in enumerate(items):
            value = item
            has_sentence_tail = re.search(r"\s+(?:is|are|was|were)\s+", value, re.IGNORECASE)
            if has_sentence_tail:
                value = re.split(r"\s+(?:is|are|was|were)\s+", value, maxsplit=1, flags=re.IGNORECASE)[0]
            if (
                item_index == len(items) - 1
                and (index + 1 < len(markers) or has_sentence_tail)
            ):
                normalized = re.sub(r"\s+", " ", value).strip()
                words = normalized.split()
                original_word_count = len(words)
                previous_last_words = {
                    candidate.split()[-1].casefold().rstrip("s")
                    for candidate in candidates
                    if candidate.split()
                }
                while len(words) > 1 and words[-1].casefold().rstrip("s") in previous_last_words:
                    words.pop()
                if len(words) < original_word_count:
                    value = " ".join(words)
            add_candidate(value)

    if not candidates:
        for match in re.finditer(
            r"(?<![\w])([A-Z][A-Za-z0-9/&()'\-]*(?:\s+[A-Za-z0-9/&()'\-]+){0,5})\s*:",
            text,
        ):
            add_candidate(match.group(1))

    return candidates


def _topic_usage_count(topic: str, previous_questions: list[str]) -> int:
    ignored_words = {"a", "an", "and", "of", "the", "to"}

    def normalize_words(text: str) -> set[str]:
        words = re.findall(r"[a-z0-9]+", text.casefold())
        normalized = set()
        for word in words:
            if word.endswith("ies") and len(word) > 4:
                word = word[:-3] + "y"
            elif word.endswith("s") and len(word) > 3:
                word = word[:-1]
            normalized.add(word)
        return normalized

    topic_words = normalize_words(topic) - ignored_words
    if not topic_words:
        return 0
    unique_questions = set(previous_questions)
    return sum(
        topic_words.issubset(normalize_words(question))
        for question in unique_questions
    )


def _assign_auto_topic_hints(
    plan: list[dict],
    topics_by_unit: dict[int, list[str]],
    previous_questions: list[str] | None = None,
) -> None:
    previous_questions = previous_questions or []
    ranked_topics = {
        unit: [
            topic
            for _, topic in sorted(
                enumerate(topics),
                key=lambda item: (
                    _topic_usage_count(item[1], previous_questions),
                    item[0],
                ),
            )
        ]
        for unit, topics in topics_by_unit.items()
    }
    offsets: dict[int, int] = {}
    for slot in plan:
        if slot.get("topic_hint"):
            continue
        unit_number = int(slot["unit"])
        topics = ranked_topics.get(unit_number) or []
        offset = offsets.get(unit_number, 0)
        if offset < len(topics):
            slot["topic_hint"] = topics[offset]
            offsets[unit_number] = offset + 1


def generate_unique_question(*, subject: dict, slot: dict, context: str,
                             previous_questions: list[str], max_attempts: int = 3) -> dict | None:
    """Generate a question that is not too similar to stored or already accepted questions."""
    subject_id = str(subject["_id"])
    avoid = list(dict.fromkeys(
        question.strip() for question in previous_questions
        if isinstance(question, str) and question.strip()
    ))
    topic_hint = _slot_topic_hint(subject, slot, context)
    candidate_count = 1 if slot.get("topic_hint") else 2
    last_rejected_question = None

    for attempt in range(1, max_attempts + 1):
        variation_instruction = ""
        if attempt == 1:
            variation_instruction = f"Focus on the named concept '{topic_hint}'. " if slot.get("topic_hint") else ""
            variation_instruction += (
                f"Return {candidate_count} distinct candidates about different named concepts; "
                "do not paraphrase previous questions or use generic filler."
            )
        elif last_rejected_question:
            if slot.get("topic_hint"):
                variation_instruction = (
                    "Earlier candidates were rejected as duplicates. Do not repeat or paraphrase "
                    f"this question: {last_rejected_question} Keep the question focused on "
                    f"'{topic_hint}', but test a different aspect and use a different question form."
                )
            else:
                variation_instruction = (
                    "Earlier candidates were rejected as duplicates. Do not reuse this question "
                    f"or its main concept: {last_rejected_question} "
                    "Choose a different named concept from this unit's syllabus and change the question form."
                )

        candidates = ai_service.generate_questions(
            subject=subject,
            unit=slot["unit"],
            topic_hint=topic_hint,
            count=candidate_count if attempt == 1 else 1,
            marks=slot["marks"],
            difficulty=slot["difficulty"],
            bloom=slot["bloom_level"],
            qtype=slot["question_type"],
            context=context,
            previous_questions=avoid[-20:],
            variation_instruction=variation_instruction,
        )
        if not candidates:
            continue

        for candidate in candidates:
            is_duplicate, score, matched = rag_service.is_duplicate(
                subject_id, candidate["question"], extra_pool=avoid
            )
            if is_duplicate:
                logger.info(
                    "Rejected duplicate candidate for unit %s (attempt %d/%d, similarity %.3f)",
                    slot["unit"], attempt, max_attempts, score,
                )
                last_rejected_question = matched or candidate["question"]
                avoid.append(candidate["question"])
                continue

            candidate.update({
                "similarity_score": score,
                "duplicate": False,
                "matched_question": None,
            })
            return candidate

    return None


def create_generation_job(*, subject_id: str, pattern: dict, units: list[int],
                          unit_weights: dict | None = None, topic_hints: dict | None = None,
                          difficulty: str = "",
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

    _assign_topic_hints(plan, topic_hints)

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
        topics_by_unit = {}
        for unit in dict.fromkeys(int(slot["unit"]) for slot in plan):
            if any(int(slot["unit"]) == unit and not slot.get("topic_hint") for slot in plan):
                topic_passages = rag_service.retrieve(
                    subject_id,
                    f"Unit {unit} syllabus outline topic headings",
                    unit=unit,
                    top_k=12,
                    doc_types=["syllabus", "textbook", "notes"],
                )
                topic_context = rag_service.build_context(topic_passages, max_chars=6000)
                topics_by_unit[unit] = _extract_topic_candidates(topic_context)
        _assign_auto_topic_hints(plan, topics_by_unit, previous)
        db.generation_jobs().update_one(
            {"job_id": job_id},
            {"$set": {"plan": plan, "updated_at": db.utcnow()}},
        )

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

            # Retry generation while excluding earlier and already accepted questions.
            cand = None
            slot_error = None

            if not context.strip():
                slot_error = (
                    f"No syllabus or notes context was retrieved for unit {slot['unit']}. "
                    "Upload course material for this unit and retry."
                )
            else:
                for attempt in range(1, 3):
                    try:
                        cand = generate_unique_question(
                            subject=subject,
                            slot=slot,
                            context=context,
                            previous_questions=previous + [
                                q["question"] for q in accepted_questions
                            ],
                        )
                        if cand:
                            break
                        slot_error = (
                            "Ollama returned only duplicate candidates after 3 attempts. "
                            "Specify distinct topics for the selected unit and retry."
                        )
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

        # Finalize job
        final_status = "completed" if len(accepted_questions) == len(plan) else "completed_with_errors"
        final_stage = (
            "Question paper generation completed successfully."
            if final_status == "completed"
            else "Question paper generation completed with errors."
        )
        db.generation_jobs().update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": final_status,
                    "current_stage": final_stage,
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
    previous.extend(
        q["question"] for q in job.get("questions", [])
        if q.get("index") != slot_index and q.get("question")
    )

    query = f"Unit {slot['unit']} {slot.get('topic_hint', '')} {slot['question_type']} key concepts"
    passages = rag_service.retrieve(subject_id, query, unit=slot["unit"], top_k=3)
    context = rag_service.build_context(passages, max_chars=1400)

    cand = generate_unique_question(
        subject=subject,
        slot=slot,
        context=context,
        previous_questions=previous,
    )

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
        "status": "accepted",
    })

    # Update in questions array inside generation_jobs
    db.generation_jobs().update_one(
        {"job_id": job_id, "questions.index": slot_index},
        {"$set": {"questions.$": cand, "updated_at": db.utcnow()}}
    )
    return cand
