"""AI service abstraction for Question Generation, Answer Keys, and Lesson Plans.

Supported providers implementing the AIProvider interface:
  * CloudProvider   -> Fast cloud LLM (Groq / Grok / OpenAI-compatible endpoint).
  * OllamaProvider  -> Local Ollama (e.g. llama3.2:1b).
  * MockProvider    -> Deterministic fallback for local/offline testing.

Provider selection is configured via AI_PROVIDER in .env:
  AI_PROVIDER=groq   (or grok)
  AI_PROVIDER=ollama
  AI_PROVIDER=mock
"""
from __future__ import annotations

import json
import logging
import re
import time
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

SYSTEM_PROMPT = (
    "You are an expert examination question-paper setter for an accredited engineering university. "
    "You must ONLY use the provided syllabus and educational excerpts. "
    "Rules:\n"
    "1. Generate questions strictly from the provided context. Never invent syllabus topics.\n"
    "2. Respect the requested unit, marks, difficulty, and Bloom's taxonomy level.\n"
    "3. Avoid questions that duplicate the listed previous questions.\n"
    "4. Make each question academically rigorous, clear, and unambiguous.\n"
    "5. Return ONLY valid JSON matching the exact schema requested. No markdown, no conversational commentary."
)

LESSON_PLAN_SYSTEM_PROMPT = (
    "You are an academic curriculum and lesson-planning coordinator for an NBA-accredited university. "
    "Based on the uploaded syllabus, generate a structured outcome-based course plan. "
    "Follow Outcome-Based Education (OBE) principles: define Course Objectives, Course Outcomes (CO1-CO5) "
    "mapped to Bloom's taxonomy, Prerequisites, recommended Textbooks/References, and a detailed topic breakdown. "
    "Return ONLY valid JSON matching the requested schema."
)


# ======================================================================
# Provider interface
# ======================================================================
class AIProvider:
    name: str = "base"

    def complete_json(self, system: str, user: str, max_tokens: int = 500) -> dict | list:
        raise NotImplementedError


class CloudProvider(AIProvider):
    """OpenAI-compatible cloud LLM provider adapter (Groq / Grok / OpenAI)."""

    def __init__(self, provider_name: str = "groq"):
        from openai import OpenAI

        self.name = provider_name
        self.api_key = config.CLOUD_API_KEY
        self.base_url = config.CLOUD_BASE_URL
        self.model = config.CLOUD_MODEL
        self.timeout = config.CLOUD_TIMEOUT

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "missing-key",
            timeout=self.timeout,
        )

    def complete_json(self, system: str, user: str, max_tokens: int = 1500) -> dict | list:
        if not self.api_key:
            logger.warning("No API key configured for %s. Falling back to MockProvider.", self.name)
            return MockProvider().complete_json(system, user)

        # Exponential backoff for rate limit errors (up to 3 retries)
        last_exc = None
        for attempt in range(3):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.2,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                content = resp.choices[0].message.content or "{}"
                return _loads_lenient(content)
            except Exception as exc:
                err_msg = str(exc)
                if "rate_limit_exceeded" in err_msg or "429" in err_msg:
                    wait = (attempt + 1) * 15  # 15s, 30s, 45s
                    logger.warning(
                        "Groq rate limit hit (attempt %d/3). Waiting %ds before retry...", attempt + 1, wait
                    )
                    time.sleep(wait)
                    last_exc = exc
                    continue
                # For json_validate_failed (truncated JSON), retry without json_object mode
                if "json_validate_failed" in err_msg or "json_object" in err_msg.lower():
                    logger.warning(
                        "Groq json_object mode failed (likely token truncation). "
                        "Retrying with plain text + manual JSON extraction."
                    )
                    try:
                        resp2 = self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": system + "\nIMPORTANT: Respond ONLY with valid JSON. No extra text."},
                                {"role": "user", "content": user},
                            ],
                            temperature=0.1,
                            max_tokens=max_tokens,
                        )
                        raw = resp2.choices[0].message.content or "{}"
                        return _loads_lenient(raw)
                    except Exception as exc2:
                        logger.warning("Plain-text JSON retry also failed: %s", exc2)
                        raise exc2
                raise
        if last_exc:
            raise last_exc
        return {}


class OllamaProvider(AIProvider):
    """Local Ollama LLM provider adapter."""

    name = "ollama"

    def __init__(self):
        from openai import OpenAI

        self.client = OpenAI(
            base_url=config.LLAMA_BASE_URL,
            api_key=config.LLAMA_API_KEY or "ollama",
            timeout=config.LLAMA_TIMEOUT,
        )
        self.model = config.LLAMA_MODEL

    def complete_json(self, system: str, user: str, max_tokens: int = 350) -> dict | list:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=config.LLAMA_TEMPERATURE,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
            extra_body={
                "repeat_penalty": 1.15,
                "num_predict": max_tokens,
            },
        )
        content = resp.choices[0].message.content or "{}"
        return _loads_lenient(content)


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
# Provider Factory
# ======================================================================
_PROVIDER: AIProvider | None = None


def get_provider() -> AIProvider:
    global _PROVIDER
    provider_name = (config.AI_PROVIDER or "mock").lower()

    if provider_name in ("groq", "grok", "cloud"):
        if config.CLOUD_API_KEY:
            return CloudProvider(provider_name)
        logger.warning(
            "AI_PROVIDER is set to '%s' but no API key was found. "
            "Falling back to local Ollama or Mock provider.", provider_name
        )
        return OllamaProvider() if config.LLAMA_BASE_URL else MockProvider()

    if provider_name in ("ollama", "llama"):
        return OllamaProvider()

    return MockProvider()


# ======================================================================
# High-level API used by Question & Answer routes
# ======================================================================
def generate_questions(*, subject: dict, unit: int, topic_hint: str, count: int, marks: int,
                       difficulty: str, bloom: str, qtype: str, context: str,
                       previous_questions: list[str]) -> list[dict]:
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
    try:
        result = provider.complete_json(SYSTEM_PROMPT, user, max_tokens=max(1200, 600 * count))
    except Exception as exc:
        logger.warning("Provider %s failed (%s). Falling back to MockProvider.", provider.name, exc)
        result = MockProvider().complete_json(SYSTEM_PROMPT, user)

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

    bloom_map = {"Remember": 1, "Understand": 2, "Apply": 3, "Analyze": 4, "Evaluate": 5, "Create": 6}
    default_bl = bloom_map.get(bloom, 2)

    norm = []
    for q in questions or []:
        if isinstance(q, str):
            q = {"question": q}
        elif not isinstance(q, dict):
            continue

        q_text = _clean_text(str(q.get("question", "")))
        if not q_text:
            continue

        q_bloom = str(q.get("bloom_level") or bloom).capitalize()
        bl_val = int(q.get("bl") or bloom_map.get(q_bloom, default_bl))

        norm.append(
            {
                "question": q_text,
                "unit": int(q.get("unit", unit) or unit),
                "topic": _clean_text(str(q.get("topic") or topic_hint or "General")),
                "marks": int(q.get("marks", marks) or marks),
                "difficulty": str(q.get("difficulty") or difficulty).capitalize(),
                "bloom_level": q_bloom,
                "question_type": str(q.get("type") or q.get("question_type") or qtype).capitalize(),
                "bl": bl_val,
                "co": int(q.get("co") or min(5, max(1, unit))),
                "po": int(q.get("po") or 3),
                "pso": int(q.get("pso") or 2),
            }
        )

    valid = [q for q in norm if len(q["question"]) > 10]
    if not valid:
        return MockProvider()._questions(
            {
                "context": context,
                "unit": unit,
                "count": count,
                "marks": marks,
                "difficulty": difficulty,
                "bloom": bloom,
                "qtype": qtype,
                "previous": previous_questions,
            }
        )
    return valid


def generate_answer(*, question: dict, context: str) -> str:
    """Generates an answer key with depth scaled according to question marks.

    Uses plain-text generation (no json_object mode) to avoid Groq's JSON
    truncation error when answer text exceeds available token budget.
    """
    marks = question.get("marks", 6)
    if marks <= 3:
        depth = "Write a concise answer in 2-4 sentences covering definition and key points."
    elif marks <= 6:
        depth = "Write a structured answer with: 1) Definition, 2) Explanation, 3) Example. Around 150-200 words."
    else:
        depth = (
            "Write a detailed answer covering: 1) Definition, 2) Explanation, "
            "3) Algorithm or Steps, 4) Example with trace, 5) Time/Space complexity. Around 300 words."
        )

    system = (
        "You are an expert examination answer-key writer for an engineering university. "
        "Use only the provided context. Write the answer directly as plain text — no JSON, no markdown code blocks."
    )
    user_text = (
        f"Question: {question['question']}\n"
        f"Topic: {question.get('topic', '')}\n"
        f"Marks: {marks}\n"
        f"Context: {context[:1800]}\n\n"
        f"Instructions: {depth}\n"
        "Write only the answer text below:\n"
    )

    provider = get_provider()
    answer_max_tokens = 400 if marks <= 3 else (700 if marks <= 6 else 1000)

    try:
        if isinstance(provider, CloudProvider):
            # Use plain-text mode for answers to avoid json truncation
            resp = provider.client.chat.completions.create(
                model=provider.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_text},
                ],
                temperature=0.3,
                max_tokens=answer_max_tokens,
            )
            raw = resp.choices[0].message.content or ""
            return _clean_text(raw.strip())
        else:
            # Ollama/Mock: use json schema path
            user_json = json.dumps(
                {
                    "task": "answer",
                    "question": question["question"],
                    "topic": question.get("topic"),
                    "marks": marks,
                    "context": context[:1800],
                    "instructions": depth,
                    "output_schema": {"answer": "string"},
                }
            )
            result = provider.complete_json(SYSTEM_PROMPT, user_json, max_tokens=answer_max_tokens)
            if isinstance(result, dict):
                return _clean_text(str(result.get("answer") or result.get("text") or ""))
            return _clean_text(str(result))
    except Exception as exc:
        logger.warning("Answer generation failed via %s: %s. Using MockProvider.", provider.name, exc)
        # Graceful fallback using Mock
        spec = {
            "context": context,
            "topic": question.get("topic", ""),
            "marks": marks,
        }
        return _clean_text(MockProvider()._answer(spec))


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
                "prerequisites": ["string"],
                "course_objectives": ["string"],
                "course_outcomes": [
                    {"co": "CO1", "text": "string", "bloom": "string", "unit": 1}
                ],
                "textbooks": [{"title": "string", "author": "string", "edition": "string", "publisher": "string"}],
                "references": [{"title": "string", "author": "string", "edition": "string", "publisher": "string"}],
            },
        }
    )

    provider = get_provider()
    try:
        # Keep lesson plan payload small enough for Groq's TPM; 1500 tokens is safe
        result = provider.complete_json(LESSON_PLAN_SYSTEM_PROMPT, user, max_tokens=1500)
    except Exception as exc:
        logger.warning("Lesson plan AI generation failed (%s). Using deterministic OBE composer.", exc)
        result = MockProvider().complete_json(LESSON_PLAN_SYSTEM_PROMPT, user)

    if isinstance(result, dict) and "course_outcomes" in result:
        return result
    return MockProvider()._lesson_plan({"subject_name": subject.get("name")})


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
