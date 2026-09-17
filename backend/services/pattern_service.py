"""Previous-question-paper pattern analysis + automatic pattern selection."""
import re
from collections import Counter

# question line like:  "1. a) Explain ... (6)"  or  "Q5 Define ... [2 marks] [Unit 3]"
_Q_LINE_RE = re.compile(
    r"^\s*(?:Q\.?\s*)?(\d{1,2})[.)]?\s*(?:([a-e])[.)])?\s*(.+?)\s*"
    r"[\[(]\s*(\d{1,2})\s*(?:marks?|m)?\s*[\])]\s*"
    r"(?:\[[^\]]*\]\s*)?$",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(r"^\s*(?:section|part)\s*[-:]?\s*([A-D])\b.*$", re.IGNORECASE)
_UNIT_HINT_RE = re.compile(r"\bunit\s*[-:]?\s*(\d)\b", re.IGNORECASE)

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
    for line in text.splitlines():
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
        qm = _Q_LINE_RE.match(line)
        if qm:
            qtext = qm.group(3).strip()
            marks = int(qm.group(4))
            um = _UNIT_HINT_RE.search(line)
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
    return questions, sections


def _dominant_sections(structures: list[list[dict]]):
    if not structures:
        return []
    key = Counter(tuple((s["section"], s["count"], s["marks_each"]) for s in st) for st in structures)
    best = key.most_common(1)[0][0]
    return [{"section": s, "count": c, "marks_each": m, "total": c * m} for s, c, m in best]


def suggest_pattern(marks_counter: Counter, structures: list[list[dict]]) -> dict:
    if structures:
        sec = _dominant_sections(structures)
        if sec:
            return {
                "name": "Derived from previous papers",
                "sections": sec,
                "total_marks": sum(s["total"] for s in sec),
            }
    # fall back to the classic 20 + 30 + 50 pattern
    return default_patterns()[0]


def default_patterns() -> list[dict]:
    return [
        {
            "name": "Standard 100 (2/6/10)",
            "sections": [
                {"section": "A", "count": 10, "marks_each": 2, "total": 20},
                {"section": "B", "count": 5, "marks_each": 6, "total": 30},
                {"section": "C", "count": 5, "marks_each": 10, "total": 50},
            ],
            "total_marks": 100,
        },
        {
            "name": "10+5+5 (2/8/12)",
            "sections": [
                {"section": "A", "count": 10, "marks_each": 2, "total": 20},
                {"section": "B", "count": 5, "marks_each": 8, "total": 40},
                {"section": "C", "count": 5, "marks_each": 8, "total": 40},
            ],
            "total_marks": 100,
        },
        {
            "name": "8+6+6 (2/5/10)",
            "sections": [
                {"section": "A", "count": 8, "marks_each": 2, "total": 16},
                {"section": "B", "count": 6, "marks_each": 4, "total": 24},
                {"section": "C", "count": 6, "marks_each": 10, "total": 60},
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
    weights = _resolve_weights(units, unit_weights)
    slots: list[dict] = []
    ui = 0
    order = _weighted_unit_order(units, weights)
    for section in pattern["sections"]:
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
