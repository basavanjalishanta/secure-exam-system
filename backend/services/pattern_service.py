"""Previous-question-paper pattern analysis + automatic pattern selection."""
import re
from collections import Counter

# Question lines vary substantially after PDF extraction. In particular, VTU
# papers often extract as ``01 a) Question text 6`` (with no brackets around
# the marks) and wrap a single question across several lines.
_Q_LINE_RE = re.compile(
    r"^\s*(?:Q(?:uestion)?\.?\s*)?(?P<number>\d{1,2})\s*[.)-]?\s*"
    r"(?:\(?[a-e]\)?[.)]\s*)?(?P<text>.+?)\s*"
    r"(?:"
    r"(?:\[\s*|\(\s*)(?P<bracket_marks>\d{1,2})\s*(?:marks?|m)?\s*(?:\]|\))"
    r"|\s+(?P<plain_marks>\d{1,2})"
    r")"
    r"(?:\s*\[?\s*(?:unit|module)\s*[-:]?\s*\d+\s*\]?)?\s*$",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(r"^\s*(?:section|part)\s*[-:]?\s*([A-D])\b.*$", re.IGNORECASE)
_UNIT_HINT_RE = re.compile(r"\bunit\s*[-:]?\s*(\d)\b", re.IGNORECASE)
_QUESTION_START_RE = re.compile(
    r"^\s*(?:Q(?:uestion)?\.?\s*)?\d{1,2}\s*[.)-]?\s+(?:\(?[a-e]\)?[.)]\s+)?"
    r"|^\s*\(?[a-e]\)?[.)]\s+",
    re.IGNORECASE,
)
_QUESTION_NUMBER_RE = re.compile(
    r"^\s*(?:Q(?:uestion)?\.?\s*)?(\d{1,2})\b",
    re.IGNORECASE,
)
_TRAILING_MARK_RE = re.compile(
    r"(?:[\[(]\s*\d{1,2}\s*(?:marks?|m)?\s*[\])]|\s+\d{1,2})\s*$",
    re.IGNORECASE,
)
_NON_MARK_NUMBER_RE = re.compile(r"\b(?:by|of|to|at|for)\s+\d{1,2}\s*$", re.IGNORECASE)

_DIFFICULTY_VERBS = {
    "Easy": ["define", "list", "state", "name", "what is", "write short"],
    "Medium": ["explain", "describe", "discuss", "differentiate", "compare"],
    "Hard": ["analyze", "evaluate", "justify", "design", "derive", "prove", "critically"],
}
_TYPE_HINTS = {
    "Numerical": ["calculate", "compute", "find the value", "solve", "evaluate the"],
    "Analytical": ["analyze", "compare", "differentiate", "why", "critically"],
    "Application": ["apply", "design", "implement", "write a query", "construct", "develop"],
}


def analyze_papers(texts: list[str]) -> dict:
    """Analyze a list of previous-paper plaintexts -> aggregate statistics."""
    all_questions: list[dict] = []
    section_structures: list[list[dict]] = []

    for text in texts:
        qs, sections = _parse_one(text)
        all_questions.extend(qs)
        if sections:
            section_structures.append(sections)

    if not all_questions:
        return {
            "papers_analyzed": len(texts),
            "questions_found": 0,
            "note": "No parseable question lines found. Provide papers with marks like 'Explain X (6)'.",
        }

    marks_counter = Counter(q["marks"] for q in all_questions)
    unit_counter = Counter(q["unit"] for q in all_questions if q["unit"])
    type_counter = Counter(q["type"] for q in all_questions)
    diff_counter = Counter(q["difficulty"] for q in all_questions)

    total_units = sum(unit_counter.values()) or 1
    unit_distribution = {
        f"unit_{u}": round(100 * c / total_units, 1) for u, c in sorted(unit_counter.items())
    }

    norm = [_normalize_q(q["text"]) for q in all_questions]
    repeats = [t for t, c in Counter(norm).items() if c > 1]
    topic_counter = Counter()
    for q in all_questions:
        for kw in _keywords(q["text"]):
            topic_counter[kw] += 1

    return {
        "papers_analyzed": len(texts),
        "questions_found": len(all_questions),
        "marks_distribution": {str(k): v for k, v in sorted(marks_counter.items())},
        "question_type_distribution": dict(type_counter),
        "difficulty_distribution": dict(diff_counter),
        "unit_distribution_percent": unit_distribution,
        "frequently_asked_topics": [t for t, _ in topic_counter.most_common(15)],
        "repeated_questions": repeats[:20],
        "repeated_question_count": len(repeats),
        "section_structure": _dominant_sections(section_structures),
        "suggested_pattern": suggest_pattern(marks_counter, section_structures),
    }


def _parse_one(text: str):
    questions, sections = [], []
    current_section = None
    current_question_number: str | None = None
    pending: list[str] = []

    def flush_pending():
        """Parse one logical question assembled from wrapped PDF lines."""
        nonlocal pending
        if not pending:
            return
        joined = " ".join(pending)
        pending = []
        qm = _Q_LINE_RE.match(joined)
        if not qm:
            return
        qtext = qm.group("text").strip()
        marks = int(qm.group("bracket_marks") or qm.group("plain_marks"))
        um = _UNIT_HINT_RE.search(joined)
        questions.append(
            {
                "text": qtext,
                "marks": marks,
                "section": current_section,
                "unit": int(um.group(1)) if um else _guess_unit(qtext),
                "difficulty": _classify(qtext, _DIFFICULTY_VERBS, "Medium"),
                "type": _classify(qtext, _TYPE_HINTS, "Theory"),
            }
        )

    for line in text.splitlines():
        line = line.strip()
        sm = _SECTION_RE.match(line)
        if sm:
            current_section = sm.group(1).upper()
            mm = re.search(r"(\d{1,2})\s*[x*×]\s*(\d{1,2})", line)
            if mm:
                sections.append(
                    {
                        "section": current_section,
                        "count": int(mm.group(1)),
                        "marks_each": int(mm.group(2)),
                        "total": int(mm.group(1)) * int(mm.group(2)),
                    }
                )
            continue
        if _QUESTION_START_RE.match(line):
            flush_pending()
            number_match = _QUESTION_NUMBER_RE.match(line)
            if number_match:
                current_question_number = number_match.group(1)
                pending = [line]
            elif current_question_number:
                # PDF extractors commonly put only the first sub-question's
                # number on the page: "01 a) ...", then "b) ...", "c) ...".
                # Reattach that number so every sub-question is parsed.
                pending = [f"{current_question_number} {line}"]
            else:
                pending = [line]
        elif pending:
            pending.append(line)

        # A trailing mark completes the question. Flushing here prevents
        # following BL/CO/PO metadata and page footers from being included.
        if (pending and _TRAILING_MARK_RE.search(line)
                and not _NON_MARK_NUMBER_RE.search(line)):
            flush_pending()
    flush_pending()
    return questions, sections


def _dominant_sections(structures: list[list[dict]]):
    if not structures:
        return []
    key = Counter(tuple((s["section"], s["count"], s["marks_each"]) for s in st) for st in structures)
    best = key.most_common(1)[0][0]
    return [{"section": s, "count": c, "marks_each": m, "total": c * m} for s, c, m in best]


def suggest_pattern(marks_counter: Counter, structures: list[list[dict]]) -> dict:
    # If dominant marks indicate a 6/6/8 or 4/8/8 or 10/10 structure, suggest VTU pattern
    # e.g., if 6, 8, 10, 4 are most frequent marks
    top_marks = [m for m, _ in marks_counter.most_common(5) if m > 2]
    # Check total questions found to infer if this was an internal exam (~4-12 questions) or 100-mark semester exam
    total_q_count = sum(marks_counter.values())
    if total_q_count <= 14:
        # Internal / CIE pattern
        return default_patterns()[3]  # CIE 50 Marks (6+6+8)

    if top_marks:
        # Check if 6 and 8 are present
        if 6 in top_marks and 8 in top_marks:
            return default_patterns()[0]  # VTU 6+6+8
        elif 4 in top_marks and 8 in top_marks:
            return default_patterns()[1]  # VTU 4+8+8
        elif 10 in top_marks:
            return default_patterns()[2]  # VTU 10+10

    if structures:
        sec = _dominant_sections(structures)
        if sec:
            return {
                "name": "Derived from previous papers",
                "sections": sec,
                "total_marks": sum(s["total"] for s in sec),
            }
    # default to VTU standard pattern
    return default_patterns()[0]


def default_patterns() -> list[dict]:
    return [
        {
            "name": "VTU Standard 100 (6+6+8 per Unit, OR Choice)",
            "format": "unit_or",
            "units": 5,
            "sub_parts": [6, 6, 8],
            "marks_per_question": 20,
            "total_marks": 100,
            "exam_type": "Semester End Examination",
            "sections": [
                {"section": "Unit-I", "count": 2, "marks_each": 20, "total": 20},
                {"section": "Unit-II", "count": 2, "marks_each": 20, "total": 20},
                {"section": "Unit-III", "count": 2, "marks_each": 20, "total": 20},
                {"section": "Unit-IV", "count": 2, "marks_each": 20, "total": 20},
                {"section": "Unit-V", "count": 2, "marks_each": 20, "total": 20},
            ],
        },
        {
            "name": "VTU Standard 100 (4+8+8 per Unit, OR Choice)",
            "format": "unit_or",
            "units": 5,
            "sub_parts": [4, 8, 8],
            "marks_per_question": 20,
            "total_marks": 100,
            "exam_type": "Semester End Examination",
            "sections": [
                {"section": "Unit-I", "count": 2, "marks_each": 20, "total": 20},
                {"section": "Unit-II", "count": 2, "marks_each": 20, "total": 20},
                {"section": "Unit-III", "count": 2, "marks_each": 20, "total": 20},
                {"section": "Unit-IV", "count": 2, "marks_each": 20, "total": 20},
                {"section": "Unit-V", "count": 2, "marks_each": 20, "total": 20},
            ],
        },
        {
            "name": "VTU Standard 100 (10+10 per Unit, OR Choice)",
            "format": "unit_or",
            "units": 5,
            "sub_parts": [10, 10],
            "marks_per_question": 20,
            "total_marks": 100,
            "exam_type": "Semester End Examination",
            "sections": [
                {"section": "Unit-I", "count": 2, "marks_each": 20, "total": 20},
                {"section": "Unit-II", "count": 2, "marks_each": 20, "total": 20},
                {"section": "Unit-III", "count": 2, "marks_each": 20, "total": 20},
                {"section": "Unit-IV", "count": 2, "marks_each": 20, "total": 20},
                {"section": "Unit-V", "count": 2, "marks_each": 20, "total": 20},
            ],
        },
        {
            "name": "CIE / Internals 50 Marks (2 Units, 6+6+8 OR Choice, Q1-Q4)",
            "format": "unit_or",
            "units": 2,
            "sub_parts": [6, 6, 8],
            "marks_per_question": 20,
            "total_marks": 50,
            "exam_type": "Continuous Internal Evaluation (CIE)",
            "sections": [
                {"section": "Unit-I", "count": 2, "marks_each": 25, "total": 25},
                {"section": "Unit-II", "count": 2, "marks_each": 25, "total": 25},
            ],
        },
        {
            "name": "CIE / Internals 50 Marks (2 Units, 10+15 OR Choice, Q1-Q4)",
            "format": "unit_or",
            "units": 2,
            "sub_parts": [10, 15],
            "marks_per_question": 25,
            "total_marks": 50,
            "exam_type": "Continuous Internal Evaluation (CIE)",
            "sections": [
                {"section": "Unit-I", "count": 2, "marks_each": 25, "total": 25},
                {"section": "Unit-II", "count": 2, "marks_each": 25, "total": 25},
            ],
        },
        {
            "name": "CIE / Internals 50 Marks (5 Units, 10 Marks each with OR)",
            "format": "unit_or",
            "units": 5,
            "sub_parts": [5, 5],
            "marks_per_question": 10,
            "total_marks": 50,
            "exam_type": "Continuous Internal Evaluation (CIE)",
            "sections": [
                {"section": "Unit-I", "count": 2, "marks_each": 10, "total": 10},
                {"section": "Unit-II", "count": 2, "marks_each": 10, "total": 10},
                {"section": "Unit-III", "count": 2, "marks_each": 10, "total": 10},
                {"section": "Unit-IV", "count": 2, "marks_each": 10, "total": 10},
                {"section": "Unit-V", "count": 2, "marks_each": 10, "total": 10},
            ],
        },
        {
            "name": "Standard 100 (2/6/10 Sectional)",
            "sections": [
                {"section": "A", "count": 10, "marks_each": 2, "total": 20},
                {"section": "B", "count": 5, "marks_each": 6, "total": 30},
                {"section": "C", "count": 5, "marks_each": 10, "total": 50},
            ],
            "total_marks": 100,
        },
        {
            "name": "50 marks internal (2/6)",
            "sections": [
                {"section": "A", "count": 10, "marks_each": 2, "total": 20},
                {"section": "B", "count": 5, "marks_each": 6, "total": 30},
            ],
            "total_marks": 50,
        },
    ]


def build_generation_plan(pattern: dict, units: list[int], unit_weights: dict | None = None) -> list[dict]:
    """Turn a pattern + unit weighting into per-question generation slots."""
    units = units or [1, 2, 3, 4, 5]
    slots: list[dict] = []

    # Check if this is a VTU Unit-OR pattern
    if pattern.get("format") == "unit_or" or "sub_parts" in pattern:
        sub_parts = pattern.get("sub_parts") or [6, 6, 8]
        sub_labels = ["a", "b", "c", "d", "e"]

        for u_idx, u in enumerate(units):
            fq_base = u_idx * 2 + 1  # 1, 3, 5, 7, 9

            # Question group 1 (Main Question, e.g. Q01)
            for sp_idx, marks in enumerate(sub_parts):
                slots.append({
                    "section": f"Unit-{u}",
                    "unit": u,
                    "marks": marks,
                    "difficulty": _difficulty_for_marks(marks),
                    "bloom_level": _bloom_for_marks(marks),
                    "question_type": "Theory" if marks <= 2 else "Analytical" if marks >= 10 else "Application",
                    "full_question_num": fq_base,
                    "sub_part": sub_labels[sp_idx % len(sub_labels)],
                    "is_or": False,
                })

            # Question group 2 (OR Question, e.g. Q02)
            for sp_idx, marks in enumerate(sub_parts):
                slots.append({
                    "section": f"Unit-{u}",
                    "unit": u,
                    "marks": marks,
                    "difficulty": _difficulty_for_marks(marks),
                    "bloom_level": _bloom_for_marks(marks),
                    "question_type": "Theory" if marks <= 2 else "Analytical" if marks >= 10 else "Application",
                    "full_question_num": fq_base + 1,
                    "sub_part": sub_labels[sp_idx % len(sub_labels)],
                    "is_or": True,
                })
        return slots

    weights = _resolve_weights(units, unit_weights)
    ui = 0
    order = _weighted_unit_order(units, weights)
    for section in pattern.get("sections", []):
        for _ in range(section["count"]):
            unit = order[ui % len(order)]
            ui += 1
            marks = section["marks_each"]
            slots.append(
                {
                    "section": section["section"],
                    "unit": unit,
                    "marks": marks,
                    "difficulty": _difficulty_for_marks(marks),
                    "bloom_level": _bloom_for_marks(marks),
                    "question_type": "Theory" if marks <= 2 else "Analytical" if marks >= 10 else "Application",
                }
            )
    return slots


def _resolve_weights(units, unit_weights):
    if unit_weights:
        return {int(k.replace("unit_", "")) if isinstance(k, str) else int(k): float(v)
                for k, v in unit_weights.items()}
    return {u: 1.0 for u in units}


def _weighted_unit_order(units, weights):
    order = []
    scaled = {u: max(1, round(weights.get(u, 1.0) * 10)) for u in units}
    maxrep = max(scaled.values())
    for rep in range(maxrep):
        for u in units:
            if scaled[u] > rep:
                order.append(u)
    return order or list(units)


def _difficulty_for_marks(m):
    return "Easy" if m <= 2 else "Medium" if m <= 6 else "Hard"


def _bloom_for_marks(m):
    return "Remember" if m <= 2 else "Understand" if m <= 6 else "Analyze"


# --- small text classifiers ---
def _classify(text: str, table: dict, default: str) -> str:
    low = text.lower()
    for label, hints in table.items():
        if any(h in low for h in hints):
            return label
    return default


def _guess_unit(text: str):
    m = _UNIT_HINT_RE.search(text)
    return int(m.group(1)) if m else None


_STOP = set("the a an of to in and or is are for with on by as explain describe discuss define "
            "list state write give differentiate compare what why how".split())


def _keywords(text: str):
    words = re.findall(r"[A-Za-z][A-Za-z-]{2,}", text)
    return [w.lower() for w in words if w.lower() not in _STOP][:6]


def _normalize_q(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()