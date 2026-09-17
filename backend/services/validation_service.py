"""Validation engine for a generated question paper."""
from collections import Counter

from config import config
from services import rag_service


def validate_paper(*, subject: dict, pattern: dict, questions: list[dict],
                    context_by_index: dict[int, str] | None = None) -> dict:
    context_by_index = context_by_index or {}
    checks: list[dict] = []
    errors: list[dict] = []

    # 1. total marks
    total = sum(int(q.get("marks", 0)) for q in questions)
    expected = pattern.get("total_marks", sum(s["total"] for s in pattern["sections"]))
    ok = total == expected
    checks.append({"check": "Total marks", "ok": ok, "detail": f"{total}/{expected}"})
    if not ok:
        errors.append({"type": "total_marks", "message": f"Total marks {total} != expected {expected}"})

    # 2. section structure
    by_section = Counter(q.get("section") for q in questions)
    for s in pattern["sections"]:
        have = by_section.get(s["section"], 0)
        sok = have == s["count"]
        checks.append(
            {"check": f"Section {s['section']} count", "ok": sok, "detail": f"{have}/{s['count']}"}
        )
        if not sok:
            errors.append(
                {"type": "section_structure",
                 "message": f"Section {s['section']} has {have} questions, expected {s['count']}"}
            )

    # 3. unit coverage / missing units
    units_present = {int(q.get("unit")) for q in questions if q.get("unit")}
    syllabus_units = {u["unit"] if isinstance(u, dict) else int(u) for u in subject.get("units", [])}
    syllabus_units = syllabus_units or {1, 2, 3, 4, 5}
    missing = sorted(syllabus_units - units_present)
    checks.append({"check": "Unit coverage", "ok": not missing,
                   "detail": f"covered {sorted(units_present)}"})
    for u in missing:
        errors.append({"type": "missing_unit", "message": f"Unit {u} is not represented", "unit": u})

    # 4. marks distribution (no single unit > 45%)
    unit_marks = Counter()
    for q in questions:
        if q.get("unit"):
            unit_marks[int(q["unit"])] += int(q.get("marks", 0))
    skewed = [u for u, m in unit_marks.items() if total and m / total > 0.45]
    checks.append({"check": "Marks distribution balance", "ok": not skewed,
                   "detail": dict(unit_marks)})
    for u in skewed:
        errors.append({"type": "marks_distribution",
                       "message": f"Unit {u} carries more than 45% of the marks"})

    # 5. question format
    bad_format = []
    for i, q in enumerate(questions):
        text = (q.get("question") or "").strip()
        if len(text) < 12 or not text[0].isupper() or text[-1] not in ".?":
            bad_format.append(i + 1)
    checks.append({"check": "Question format", "ok": not bad_format,
                   "detail": f"issues at {bad_format}" if bad_format else "clean"})
    for i in bad_format:
        errors.append({"type": "invalid_format", "message": f"Question {i} is not well formed",
                       "question_index": i - 1})

    # 6 & 7. duplicate / similar questions (semantic)
    embeddings = rag_service.embed_texts([q.get("question", "") for q in questions])
    similar_pairs = []
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            s = rag_service.cosine(embeddings[i], embeddings[j])
            if s >= config.DUPLICATE_THRESHOLD:
                similar_pairs.append({"a": i + 1, "b": j + 1, "score": round(s, 3)})
    checks.append({"check": "No duplicate / similar questions", "ok": not similar_pairs,
                   "detail": similar_pairs or "none"})
    for p in similar_pairs:
        errors.append({"type": "similar_questions",
                       "message": f"Question {p['a']} and Question {p['b']} are too similar "
                                  f"(score {p['score']})",
                       "question_index": p["b"] - 1})

    # 8. also check against the historical question bank
    bank_dups = []
    for i, q in enumerate(questions):
        is_dup, score, matched = rag_service.is_duplicate(str(subject["_id"]), q.get("question", ""))
        if is_dup:
            bank_dups.append({"question_index": i, "score": score, "matched": matched})
    checks.append({"check": "No repeats from question bank", "ok": not bank_dups,
                   "detail": f"{len(bank_dups)} repeats"})
    for d in bank_dups:
        errors.append({"type": "duplicate_questions",
                       "message": f"Question {d['question_index'] + 1} repeats a stored question "
                                  f"(score {d['score']})",
                       "question_index": d["question_index"]})

    # 9 & 10. AI hallucination / unsupported content
    weak_support = []
    for i, q in enumerate(questions):
        ctx = context_by_index.get(i, "")
        if not ctx:
            continue
        score = rag_service.hallucination_score(q.get("question", ""), ctx)
        if score < 0.25:
            weak_support.append({"question_index": i, "support": score})
    checks.append({"check": "Content supported by uploaded material", "ok": not weak_support,
                   "detail": f"{len(weak_support)} weakly-supported"})
    for w in weak_support:
        errors.append({"type": "hallucination",
                       "message": f"Question {w['question_index'] + 1} is weakly supported by the "
                                  f"retrieved context (support {w['support']})",
                       "question_index": w["question_index"]})

    difficulty = Counter(q.get("difficulty", "Medium") for q in questions)
    checks.append({"check": "Difficulty distribution", "ok": len(difficulty) >= 2,
                   "detail": dict(difficulty)})

    return {
        "valid": len(errors) == 0,
        "checks": checks,
        "errors": errors,
        "summary": {
            "total_marks": total,
            "expected_marks": expected,
            "units_covered": sorted(units_present),
            "missing_units": missing,
            "duplicate_pairs": similar_pairs,
        },
    }
