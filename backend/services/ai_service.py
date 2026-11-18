"""Ollama-backed generation for questions, answer keys, and lesson plans."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from config import config

logger = logging.getLogger(__name__)


def _clean_text(s: str) -> str:
    if not s:
        return ""
    replacements = {
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s.strip()

BLOOM_VERBS = {
    "Remember": ["Define", "List", "State", "Identify", "Recall"],
    "Understand": ["Explain", "Describe", "Summarize", "Illustrate", "Interpret"],
    "Apply": ["Apply", "Demonstrate", "Compute", "Solve", "Develop"],
    "Analyze": ["Analyze", "Compare", "Differentiate", "Examine", "Break down"],
    "Evaluate": ["Evaluate", "Justify", "Critique", "Assess", "Argue"],
    "Create": ["Design", "Formulate", "Construct", "Develop", "Propose"],
}
_BLOOM_LEVELS = {
    "Remember": 1,
    "Understand": 2,
    "Apply": 3,
    "Analyze": 4,
    "Evaluate": 5,
    "Create": 6,
}


def _coerce_int(value: Any, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group()) if match else fallback


def _normalize_bloom(value: Any, fallback: str) -> tuple[str, int]:
    fallback_level = next(
        (level for level in _BLOOM_LEVELS if level.casefold() == str(fallback).casefold()),
        "Understand",
    )
    if value is not None:
        text = str(value).strip()
        for level, number in _BLOOM_LEVELS.items():
            if text.casefold() == level.casefold():
                return level, number
        number = _coerce_int(text, 0)
        if number in _BLOOM_LEVELS.values():
            return next(level for level, level_number in _BLOOM_LEVELS.items() if level_number == number), number
    return fallback_level, _BLOOM_LEVELS[fallback_level]

SYSTEM_PROMPT = (
    "You are an expert examination question-paper setter for an accredited engineering university. "
    "You must ONLY use the provided syllabus and educational excerpts. "
    "Rules:\n"
    "1. Generate questions strictly from the provided context. Never invent syllabus topics.\n"
    "2. Respect the requested unit, marks, difficulty, and Bloom's taxonomy level.\n"
    "3. Avoid questions that duplicate the listed previous questions. Do not paraphrase one by changing only the verb.\n"
    "4. Make each question academically rigorous, clear, and unambiguous.\n"
    "5. Avoid generic filler such as 'based on the studied material'; name the specific syllabus concept.\n"
    "6. If multiple questions are requested, each must test a different named concept and use a distinct question form.\n"
    "7. Follow any variation_instruction and return ONLY valid JSON matching the exact schema requested."
)

ANSWER_SYSTEM_PROMPT = (
    "You are an expert university examiner writing a model answer and marking guide. "
    "Answer the supplied question exactly; do not generate or substitute questions. "
    "Use the supplied syllabus excerpts as the primary source, include the detail justified by the marks, "
    "and do not invent facts, examples, or source citations. "
    "If the supplied excerpts do not support a required detail, state that limitation clearly. "
    "Return only valid JSON matching the requested schema."
)

LESSON_PLAN_SYSTEM_PROMPT = (
    "You are an academic curriculum and lesson-planning coordinator for an NBA-accredited university. "
    "Based on the uploaded syllabus, generate a structured outcome-based course plan. "
    "Follow Outcome-Based Education (OBE) principles: define Course Objectives, Course Outcomes (CO1-CO5) "
    "mapped to Bloom's taxonomy, Prerequisites, and recommended Textbooks/References. "
    "Return ONLY valid JSON. Every requested list must be a JSON array, never a prose string."
)


# ======================================================================
# Provider interface
# ======================================================================
class AIProvider:
    name: str = "base"

    def complete_json(self, system: str, user: str, max_tokens: int = 500) -> dict | list:
        raise NotImplementedError


class AIProviderError(RuntimeError):
    """Raised when an AI provider is unavailable or returns unusable output."""


class OllamaProvider(AIProvider):
    """Local Ollama LLM provider adapter."""

    name = "ollama"

    def __init__(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AIProviderError(
                "The OpenAI-compatible client is missing. Install backend/requirements.txt."
            ) from exc

        self.client = OpenAI(
            base_url=config.OLLAMA_BASE_URL,
            api_key=config.OLLAMA_API_KEY or "ollama",
            timeout=config.OLLAMA_TIMEOUT,
        )
        self.model = config.OLLAMA_MODEL

    def complete_json(self, system: str, user: str, max_tokens: int = 350) -> dict | list:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=config.OLLAMA_TEMPERATURE,
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
                extra_body={
                    "repeat_penalty": 1.15,
                    "num_predict": max_tokens,
                },
            )
        except Exception as exc:
            logger.exception("Ollama request failed")
            raise AIProviderError(
                "Could not reach Ollama. Confirm the server is running, the configured "
                "model is installed, and OLLAMA_BASE_URL is correct."
            ) from exc

        choices = getattr(resp, "choices", None)
        if not choices:
            raise AIProviderError("Ollama returned no completion choices.")
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("Ollama returned an empty response.")
        try:
            return _loads_lenient(content)
        except (json.JSONDecodeError, TypeError) as exc:
            try:
                task = json.loads(user).get("task")
            except (json.JSONDecodeError, AttributeError):
                task = None
            if task == "answer":
                answer = _answer_from_invalid_json(content)
                if answer:
                    logger.warning("Ollama returned a non-JSON answer; preserving its text response.")
                    return {"answer": answer}
            raise AIProviderError("Ollama returned invalid JSON. Please retry generation.") from exc


class MockProvider(AIProvider):
    """Deterministic, context-derived generator for offline local testing."""

    name = "mock"

    def complete_json(self, system: str, user: str, max_tokens: int = 500) -> dict | list:
        spec = _parse_mock_user(user)
        if spec.get("task") == "questions":
            return {"questions": self._questions(spec)}
        if spec.get("task") == "answer":
            return {"answer": self._answer(spec)}
        if spec.get("task") == "lesson_plan":
            return self._lesson_plan(spec)
        return {}

    def _questions(self, spec):
        sentences = _key_sentences(spec["context"])
        previous = [p.lower() for p in spec.get("previous", [])]
        out = []
        vi = 0
        for i in range(spec.get("count", 1)):
            bloom = spec["bloom"]
            verbs = BLOOM_VERBS.get(bloom, ["Explain"])
            verb = verbs[vi % len(verbs)]
            vi += 1
            topic = _topic_from(sentences, i)
            marks = spec["marks"]
            if marks <= 4:
                stem = f"{verb} the concept of {topic} with relevant syntax or a brief example."
                qtype = "Theory"
            elif marks <= 6:
                stem = f"With a suitable example, {verb.lower()} {topic} based on the course material."
                qtype = spec.get("qtype", "Application")
            else:
                stem = (
                    f"{verb} {topic} in detail. Discuss its implementation, "
                    f"trace with an illustrative example and necessary diagrams."
                )
                qtype = spec.get("qtype", "Analytical")

            if any(_similar(stem.lower(), p) for p in previous):
                stem = f"Contrast {topic} with alternative approaches, and demonstrate its practical application."

            bloom_map = {"Remember": 1, "Understand": 2, "Apply": 3, "Analyze": 4, "Evaluate": 5, "Create": 6}
            bl_num = bloom_map.get(bloom, 2)
            unit_val = spec["unit"]

            out.append(
                {
                    "question": stem,
                    "unit": unit_val,
                    "topic": topic,
                    "marks": marks,
                    "difficulty": spec["difficulty"],
                    "bloom_level": bloom,
                    "question_type": qtype,
                    "bl": bl_num,
                    "co": min(5, max(1, unit_val)),
                    "po": 3,
                    "pso": 2,
                }
            )
        return out

    def _answer(self, spec):
        sentences = _key_sentences(spec["context"], limit=8)
        marks = spec["marks"]
        topic = spec.get("topic", "the concept")
        if marks <= 4:
            pts = sentences[:3] or [f"Core definition and significance of {topic}."]
            return "\n".join(f"• {s}" for s in pts)
        if marks <= 6:
            body = " ".join(sentences[:5])
            return (
                f"1. Definition & Core Concept:\n{sentences[0] if sentences else topic}\n\n"
                f"2. Explanation:\n{body}\n\n"
                f"3. Example / Implementation:\nRefer to the standard syntax and worked implementation for {topic}."
            )
        body = " ".join(sentences[:8])
        return (
            f"1. Theoretical Overview:\n{topic} is an essential component. {sentences[0] if sentences else ''}\n\n"
            f"2. Detailed Discussion & Algorithm/Architecture:\n{body}\n\n"
            f"3. Practical Working & Trace:\nRefer to standard test trace and diagrams provided in the textbook excerpts.\n\n"
            f"4. Conclusion & Key Takeaways:\nSummary of time/space considerations and application areas."
        )

    def _lesson_plan(self, spec):
        subject_name = spec.get("subject_name", "Engineering Subject")
        return {
            "prerequisites": [
                "Basic knowledge of foundational programming and problem solving.",
                "Elementary mathematics and discrete logic.",
            ],
            "course_objectives": [
                f"Understand foundational principles and architecture of {subject_name}.",
                f"Analyze design paradigms and practical applications of {subject_name}.",
                f"Develop efficient solutions and implement standard algorithms for {subject_name}.",
                f"Evaluate performance, trade-offs, and industrial best practices in {subject_name}.",
            ],
            "course_outcomes": [
                {"co": "CO1", "text": f"Explain foundational concepts and data representations in {subject_name}.", "bloom": "Understand", "unit": 1},
                {"co": "CO2", "text": f"Apply appropriate structures and algorithms to solve engineering problems.", "bloom": "Apply", "unit": 2},
                {"co": "CO3", "text": f"Analyze complex data manipulation techniques and memory management.", "bloom": "Analyze", "unit": 3},
                {"co": "CO4", "text": f"Design and implement non-linear abstractions and hierarchical models.", "bloom": "Analyze", "unit": 4},
                {"co": "CO5", "text": f"Evaluate and optimize application performance for real-world scenarios.", "bloom": "Evaluate", "unit": 5},
            ],
            "textbooks": [
                {"title": f"Fundamentals of {subject_name}", "author": "Standard Author", "edition": "2nd Edition", "publisher": "Pearson Education"},
            ],
            "references": [
                {"title": f"Advanced {subject_name} and Applications", "author": "Reference Author", "edition": "3rd Edition", "publisher": "McGraw-Hill"},
            ],
        }


# ======================================================================
# Provider factory
# ======================================================================
def get_provider() -> AIProvider:
    provider_name = (config.AI_PROVIDER or "ollama").lower()
    if provider_name in ("ollama", "llama"):
        return OllamaProvider()
    if provider_name == "mock":
        return MockProvider()
    raise AIProviderError(
        f"Unsupported AI_PROVIDER '{provider_name}'. Choose 'ollama' or 'mock'."
    )


# ======================================================================
# High-level API used by Question & Answer routes
# ======================================================================
def generate_questions(*, subject: dict, unit: int, topic_hint: str, count: int, marks: int,
                       difficulty: str, bloom: str, qtype: str, context: str,
                       previous_questions: list[str], variation_instruction: str = "") -> list[dict]:
    """Generates examination questions aligned strictly to syllabus context."""
    user = json.dumps(
        {
            "task": "questions",
            "subject": subject.get("name"),
            "unit": unit,
            "topic_hint": topic_hint,
            "count": count,
            "marks": marks,
            "difficulty": difficulty,
            "bloom_level": bloom,
            "question_type": qtype,
            "previous_questions": previous_questions[:20],
            "variation_instruction": variation_instruction,
            "context": context,
            "output_schema": {
                "questions": [
                    {
                        "question": "string",
                        "unit": "int",
                        "topic": "string",
                        "marks": "int",
                        "difficulty": "Easy|Medium|Hard",
                        "bloom_level": "Remember|Understand|Apply|Analyze|Evaluate|Create",
                        "type": "Theory|Numerical|Analytical|Application",
                        "bl": "int (1-6 for Bloom level)",
                        "co": "int (1-5 for Course Outcome)",
                        "po": "int (e.g. 3)",
                        "pso": "int (e.g. 2)",
                    }
                ]
            },
        }
    )

    provider = get_provider()
    result = provider.complete_json(SYSTEM_PROMPT, user, max_tokens=max(1200, 600 * count))

    questions = []
    if isinstance(result, dict):
        if "questions" in result and isinstance(result["questions"], list):
            questions = result["questions"]
        elif "question" in result:
            questions = [result]
        else:
            for val in result.values():
                if isinstance(val, list) and val and (isinstance(val[0], dict) or isinstance(val[0], str)):
                    questions = val
                    break
    elif isinstance(result, list):
        questions = result

    norm = []
    for q in questions or []:
        if isinstance(q, str):
            q = {"question": q}
        elif not isinstance(q, dict):
            continue

        q_text = _clean_text(str(q.get("question", "")))
        if not q_text:
            continue

        q_bloom, bl_val = _normalize_bloom(q.get("bloom_level") or q.get("bl"), bloom)

        norm.append(
            {
                "question": q_text,
                "unit": _coerce_int(q.get("unit", unit), unit) or unit,
                "topic": _clean_text(str(q.get("topic") or topic_hint or "General")),
                "marks": _coerce_int(q.get("marks", marks), marks) or marks,
                "difficulty": str(q.get("difficulty") or difficulty).capitalize(),
                "bloom_level": q_bloom,
                "question_type": str(q.get("type") or q.get("question_type") or qtype).capitalize(),
                "bl": bl_val,
                "co": _coerce_int(q.get("co"), min(5, max(1, unit))),
                "po": _coerce_int(q.get("po"), 3),
                "pso": _coerce_int(q.get("pso"), 2),
            }
        )

    valid = [q for q in norm if len(q["question"]) > 10]
    if not valid:
        raise AIProviderError(
            f"{provider.name} did not return any valid structured questions. Please retry generation."
        )
    return valid


def generate_answer(*, question: dict, context: str) -> str:
    """Generates an answer key with depth scaled according to question marks.

    Uses the shared JSON response path so Ollama and mock outputs are normalized consistently.
    """
    question_text = question.get("question")
    if not isinstance(question_text, str) or not question_text.strip():
        raise AIProviderError("The question is empty or invalid.")

    marks = _coerce_int(question.get("marks"), 6)
    if marks <= 3:
        depth = "Write a concise answer in 2-4 sentences covering definition and key points."
    elif marks <= 6:
        depth = "Write a structured answer with: 1) Definition, 2) Explanation, 3) Example. Around 150-200 words."
    else:
        depth = (
            "Write a detailed answer covering: 1) Definition, 2) Explanation, "
            "3) Algorithm or Steps, 4) Example with trace, 5) Time/Space complexity. Around 300 words."
        )

    provider = get_provider()
    answer_max_tokens = 400 if marks <= 3 else (700 if marks <= 6 else 1000)

    user_json = json.dumps(
        {
            "task": "answer",
            "question": question_text.strip(),
            "topic": question.get("topic"),
            "marks": marks,
            "context": context[:1800],
            "instructions": depth,
            "output_schema": {"answer": "string"},
        }
    )
    result = provider.complete_json(ANSWER_SYSTEM_PROMPT, user_json, max_tokens=answer_max_tokens)
    answer_value = result.get("answer") or result.get("text") if isinstance(result, dict) else result
    if not isinstance(answer_value, str):
        raise AIProviderError(f"{provider.name} returned an invalid answer format. Please retry generation.")
    answer = _clean_text(answer_value)
    if not answer:
        raise AIProviderError(f"{provider.name} did not return an answer. Please retry generation.")
    return answer


def generate_lesson_plan_ai(*, subject: dict, syllabus_text: str) -> dict:
    """Uses the AI provider to extract OBE Course Outcomes, Objectives, and Book references."""
    user = json.dumps(
        {
            "task": "lesson_plan",
            "subject_name": subject.get("name"),
            "subject_code": subject.get("code"),
            "semester": subject.get("semester"),
            "syllabus_excerpt": syllabus_text[:4000],
            "output_schema": {
                "prerequisites": ["up to 3 concise strings"],
                "course_objectives": ["3 concise strings, up to 15 words each"],
                "course_outcomes": [
                    {"co": "CO1", "text": "concise string of at most 18 words", "bloom": "string", "unit": 1}
                ],
                "textbooks": [{"title": "string", "author": "string", "edition": "string", "publisher": "string"}],
                "references": [{"title": "string", "author": "string", "edition": "string", "publisher": "string"}],
            },
            "constraints": [
                "Return exactly 5 course outcomes, one for each of CO1 through CO5.",
                "Return exactly 3 objectives; keep each objective and outcome concise and grounded in the syllabus.",
                "Return all fields in the exact JSON types shown in output_schema.",
            ],
        }
    )

    provider = get_provider()
    result = provider.complete_json(LESSON_PLAN_SYSTEM_PROMPT, user, max_tokens=700)

    if isinstance(result, dict) and "course_outcomes" in result:
        return result
    raise AIProviderError(
        f"{provider.name} did not return a valid lesson plan. Please retry generation."
    )


# ======================================================================
# Text parsing & Helper utilities
# ======================================================================
def _loads_lenient(text: str) -> dict | list:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        raise


def _answer_from_invalid_json(content: str) -> str:
    text = re.sub(r"^```(?:json|text)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    answer_key = re.search(r'"answer"\s*:\s*', text, re.IGNORECASE)
    if answer_key:
        value = text[answer_key.end():].strip()
        if value.startswith('"'):
            try:
                decoded, _ = json.JSONDecoder().raw_decode(value)
                if isinstance(decoded, str):
                    return _clean_text(decoded)
            except json.JSONDecodeError:
                value = value[1:]
            value = re.split(r'"\s*[,}]\s*', value, maxsplit=1)[0]
            return _clean_text(value.replace(r"\"", '"').replace(r"\n", "\n"))
        if value.startswith("'"):
            value = value[1:]
        value = re.split(r"\s*[,}]\s*", value, maxsplit=1)[0]
        return _clean_text(value.strip("'\""))
    if text.startswith(("{", "[")):
        return ""
    return _clean_text(text)


def _parse_mock_user(user: str) -> dict:
    data = json.loads(user)
    if data.get("task") == "questions":
        return {
            "task": "questions",
            "unit": data.get("unit", 1),
            "count": int(data.get("count", 1)),
            "marks": int(data.get("marks", 6)),
            "difficulty": str(data.get("difficulty", "Medium")).capitalize(),
            "bloom": str(data.get("bloom_level", "Understand")).capitalize(),
            "qtype": str(data.get("question_type", "Theory")).capitalize(),
            "context": data.get("context", ""),
            "previous": data.get("previous_questions", []),
        }
    if data.get("task") == "lesson_plan":
        return {
            "task": "lesson_plan",
            "subject_name": data.get("subject_name", "Subject"),
        }
    return {
        "task": "answer",
        "marks": int(data.get("marks", 6)),
        "topic": data.get("topic", "the concept"),
        "context": data.get("context", ""),
    }


def _key_sentences(context: str, limit: int = 40) -> list[str]:
    text = re.sub(r"\[Source \d+[^\]]*\]", " ", context)
    text = re.sub(r"(?m)^\s*(?:unit|module|chapter)\s*[-:]?\s*\d+.*$", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?m)^[A-Z0-9 ,'&()-]{12,}$", " ", text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for s in sentences:
        s = re.sub(r"\s+", " ", s).strip()
        if not (25 <= len(s) <= 260 and re.search(r"[a-z]{3}", s)):
            continue
        words = s.split()
        if len(words) < 6:
            continue
        cap_ratio = sum(1 for w in words if w[:1].isupper()) / len(words)
        if cap_ratio > 0.6:
            continue
        if sum(s.count(ch) for ch in "(){}[];*<>=") >= 2:
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


_STOP = set(
    "the a an of to in and or is are for with on by as be this that which introduction "
    "unit module chapter level part major such has have from its their been also".split()
)


def _topic_from(sentences: list[str], i: int) -> str:
    if not sentences:
        return "the given concept"
    s = sentences[i % len(sentences)]
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z-]+", s) if w.lower() not in _STOP]
    titled = [w for w in words if w[0].isupper() and (not w.isupper() or len(w) <= 4)]
    phrase = " ".join((titled or words)[:4]).strip()
    return phrase or "the given concept"


def _similar(a: str, b: str) -> bool:
    aw, bw = set(a.split()), set(b.split())
    if not aw or not bw:
        return False
    return len(aw & bw) / len(aw | bw) > 0.6
