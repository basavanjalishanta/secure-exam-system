"""AI service abstraction.

Two providers implement the same interface:

  * LlamaProvider  -> a local, LLaMA-compatible OpenAI-style endpoint
                      (Ollama, llama.cpp server, vLLM, LM Studio, ...).
                      Uploaded material stays on your infrastructure.
  * MockProvider   -> DEVELOPMENT / TESTING ONLY. It does NOT hardcode a
                      question list: it composes questions and answers from
                      the retrieved context passages using Bloom-aware
                      templates so the full pipeline (retrieval -> generation
                      -> validation -> dedup -> PDF -> encryption) can be
                      exercised without a model server.

Switch with AI_PROVIDER in .env.
"""
from __future__ import annotations

import json
import re

from config import config

BLOOM_VERBS = {
    "Remember": ["Define", "List", "State", "Identify", "Recall"],
    "Understand": ["Explain", "Describe", "Summarize", "Illustrate", "Interpret"],
    "Apply": ["Apply", "Demonstrate", "Compute", "Solve", "Use"],
    "Analyze": ["Analyze", "Compare", "Differentiate", "Examine", "Break down"],
    "Evaluate": ["Evaluate", "Justify", "Critique", "Assess", "Argue"],
    "Create": ["Design", "Formulate", "Construct", "Develop", "Propose"],
}

SYSTEM_PROMPT = (
    "You are an examination question-paper setter for a university. "
    "You must ONLY use the provided context (syllabus, textbook and notes excerpts). "
    "Rules:\n"
    "1. Generate questions strictly from the provided context. Never invent syllabus topics.\n"
    "2. Respect the requested unit, marks, difficulty and Bloom's taxonomy level.\n"
    "3. Avoid questions that duplicate the listed previous questions.\n"
    "4. Make each question academically meaningful and unambiguous.\n"
    "5. Return ONLY valid JSON. No markdown, no commentary."
)


# ======================================================================
# Provider interface
# ======================================================================
class AIProvider:
    name = "base"

    def complete_json(self, system: str, user: str) -> dict | list:
        raise NotImplementedError


class LlamaProvider(AIProvider):
    name = "llama"

    def __init__(self):
        from openai import OpenAI

        self.client = OpenAI(
            base_url=config.LLAMA_BASE_URL,
            api_key=config.LLAMA_API_KEY,
            timeout=config.LLAMA_TIMEOUT,
        )
        self.model = config.LLAMA_MODEL

    def complete_json(self, system: str, user: str) -> dict | list:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        return _loads_lenient(content)


class MockProvider(AIProvider):
    """Deterministic, context-derived generator for local testing."""

    name = "mock"

    def complete_json(self, system: str, user: str) -> dict | list:
        spec = _parse_mock_user(user)
        if spec["task"] == "questions":
            return {"questions": self._questions(spec)}
        if spec["task"] == "answer":
            return {"answer": self._answer(spec)}
        return {}

    # -- questions --
    def _questions(self, spec):
        sentences = _key_sentences(spec["context"])
        previous = [p.lower() for p in spec.get("previous", [])]
        out = []
        vi = 0
        for i in range(spec["count"]):
            bloom = spec["bloom"]
            verb = BLOOM_VERBS.get(bloom, ["Explain"])[vi % len(BLOOM_VERBS.get(bloom, ["Explain"]))]
            vi += 1
            topic = _topic_from(sentences, i)
            marks = spec["marks"]
            if marks <= 2:
                stem = f"{verb} the term '{topic}'."
                qtype = "Theory"
            elif marks <= 6:
                stem = f"{verb} {topic} with a suitable example based on the studied material."
                qtype = spec.get("qtype", "Theory")
            else:
                stem = (
                    f"{verb} {topic} in detail. Discuss its significance, "
                    f"illustrate with examples and, where appropriate, a diagram."
                )
                qtype = spec.get("qtype", "Analytical")
            if any(_similar(stem.lower(), p) for p in previous):
                stem = f"{verb} how {topic} is used in practice, and contrast it with related concepts."
            out.append(
                {
                    "question": stem,
                    "unit": spec["unit"],
                    "topic": topic,
                    "marks": marks,
                    "difficulty": spec["difficulty"],
                    "bloom_level": bloom,
                    "type": qtype,
                }
            )
        return out

    # -- answer --
    def _answer(self, spec):
        sentences = _key_sentences(spec["context"], limit=8)
        marks = spec["marks"]
        if marks <= 2:
            pts = sentences[:3] or ["Key definition based on the notes."]
            return "\n".join(f"- {s}" for s in pts)
        if marks <= 6:
            body = " ".join(sentences[:5])
            return (
                f"Definition: {sentences[0] if sentences else spec['topic']}.\n\n"
                f"Explanation: {body}\n\n"
                f"Example: As described in the notes for the topic '{spec['topic']}'."
            )
        body = " ".join(sentences[:8])
        return (
            f"Introduction: {spec['topic']} — {sentences[0] if sentences else ''}\n\n"
            f"Detailed explanation: {body}\n\n"
            f"Examples: Refer to the worked examples in the textbook/notes for '{spec['topic']}'.\n\n"
            f"Diagram: Include a labelled diagram illustrating {spec['topic']} where applicable.\n\n"
            f"Conclusion: Summary of the main points above."
        )


_PROVIDER: AIProvider | None = None


def get_provider() -> AIProvider:
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = LlamaProvider() if config.AI_PROVIDER == "llama" else MockProvider()
    return _PROVIDER


# ======================================================================
# High-level API used by the routes
# ======================================================================
def generate_questions(*, subject: dict, unit: int, topic_hint: str, count: int, marks: int,
                       difficulty: str, bloom: str, qtype: str, context: str,
                       previous_questions: list[str]) -> list[dict]:
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
            "previous_questions": previous_questions[:25],
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
                    }
                ]
            },
        }
    )
    result = get_provider().complete_json(SYSTEM_PROMPT, user)
    questions = result.get("questions", result) if isinstance(result, dict) else result
    norm = []
    for q in questions or []:
        # Smaller/weaker local models sometimes ignore the object schema and
        # return a plain list of question strings instead of objects -
        # fall back to the requested defaults for every other field.
        if isinstance(q, str):
            q = {"question": q}
        elif not isinstance(q, dict):
            continue
        norm.append(
            {
                "question": str(q.get("question", "")).strip(),
                "unit": int(q.get("unit", unit) or unit),
                "topic": str(q.get("topic") or topic_hint or "General").strip(),
                "marks": int(q.get("marks", marks) or marks),
                "difficulty": str(q.get("difficulty") or difficulty).capitalize(),
                "bloom_level": str(q.get("bloom_level") or bloom).capitalize(),
                "question_type": str(q.get("type") or q.get("question_type") or qtype).capitalize(),
            }
        )
    return [q for q in norm if q["question"]]


def generate_answer(*, question: dict, context: str) -> str:
    user = json.dumps(
        {
            "task": "answer",
            "question": question["question"],
            "topic": question.get("topic"),
            "marks": question.get("marks"),
            "context": context,
            "instructions": "Answer only from the context. Depth must match the marks.",
            "output_schema": {"answer": "string"},
        }
    )
    result = get_provider().complete_json(SYSTEM_PROMPT, user)
    if isinstance(result, dict):
        return str(result.get("answer", "")).strip()
    return str(result).strip()


# ======================================================================
# helpers
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
    return {
        "task": "answer",
        "marks": int(data.get("marks", 6)),
        "topic": data.get("topic", "the topic"),
        "context": data.get("context", ""),
    }


def _key_sentences(context: str, limit: int = 40) -> list[str]:
    # drop the "[Source n | ...]" markers and heading lines
    text = re.sub(r"\[Source \d+[^\]]*\]", " ", context)
    text = re.sub(r"(?m)^\s*(?:unit|module|chapter)\s*[-:]?\s*\d+.*$", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?m)^[A-Z0-9 ,'&()-]{12,}$", " ", text)  # ALL-CAPS heading lines
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for s in sentences:
        s = re.sub(r"\s+", " ", s).strip()
        if not (25 <= len(s) <= 260 and re.search(r"[a-z]{3}", s)):
            continue
        words = s.split()
        if len(words) < 6:
            continue
        # skip name/title-like fragments (headers, faculty names, running
        # titles) that slipped through: mostly-capitalized, few lowercase
        # function words, i.e. not an actual sentence.
        cap_ratio = sum(1 for w in words if w[:1].isupper()) / len(words)
        if cap_ratio > 0.6:
            continue
        # skip code/syntax fragments common in technical notes
        # (function calls, pointer syntax, malloc(byte-size); etc.)
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
    # prefer Title-case terms, but drop ALL-CAPS shouting unless it's a short acronym
    titled = [w for w in words if w[0].isupper() and (not w.isupper() or len(w) <= 4)]
    phrase = " ".join((titled or words)[:4]).strip()
    return phrase or "the given concept"


def _similar(a: str, b: str) -> bool:
    aw, bw = set(a.split()), set(b.split())
    if not aw or not bw:
        return False
    return len(aw & bw) / len(aw | bw) > 0.6
