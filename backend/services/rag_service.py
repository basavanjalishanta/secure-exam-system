"""Retrieval-Augmented Generation pipeline.

- Embedding provider abstraction (hash fallback / sentence-transformers / llama)
- Vector store backed by MongoDB `chunks` collection
- Cosine similarity retrieval computed locally with numpy
- Semantic similarity used for duplicate detection

No uploaded examination material ever leaves this machine.
"""
import hashlib
import math
import re

import numpy as np

from config import config
from models import db

_ST_MODEL = None


# ---------------- Embedding providers ----------------
def _hash_embedding(text: str, dim: int) -> list[float]:
    """Deterministic bag-of-words hashing embedding. Zero external deps.

    Good enough for local semantic similarity / duplicate detection in a
    college-project setting; swap EMBEDDING_PROVIDER for a real model in prod.
    """
    vec = np.zeros(dim, dtype=np.float32)
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec.tolist()


def _sentence_transformer_embedding(texts: list[str]) -> list[list[float]]:
    global _ST_MODEL
    if _ST_MODEL is None:
        from sentence_transformers import SentenceTransformer

        _ST_MODEL = SentenceTransformer(config.EMBEDDING_MODEL)
    return [v.tolist() for v in _ST_MODEL.encode(texts, normalize_embeddings=True)]


def _llama_embedding(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(base_url=config.LLAMA_BASE_URL, api_key=config.LLAMA_API_KEY)
    resp = client.embeddings.create(model=config.EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    provider = config.EMBEDDING_PROVIDER
    if provider == "sentence-transformers":
        return _sentence_transformer_embedding(texts)
    if provider == "llama":
        return _llama_embedding(texts)
    return [_hash_embedding(t, config.EMBEDDING_DIM) for t in texts]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


# ---------------- Similarity ----------------
def cosine(a, b) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ---------------- Vector store (MongoDB) ----------------
def index_chunks(subject_id: str, document_id: str, doc_type: str, chunks: list[dict]):
    if not chunks:
        return 0
    embeddings = embed_texts([c["text"] for c in chunks])
    rows = []
    for c, emb in zip(chunks, embeddings):
        rows.append(
            {
                "subject_id": subject_id,
                "document_id": document_id,
                "doc_type": doc_type,
                "text": c["text"],
                "unit": c.get("unit"),
                "index": c.get("index"),
                "embedding": emb,
                "created_at": db.utcnow(),
            }
        )
    db.chunks().insert_many(rows)
    return len(rows)


def retrieve(subject_id: str, query: str, unit: int | None = None, top_k: int | None = None,
             doc_types: list[str] | None = None) -> list[dict]:
    top_k = top_k or config.RAG_TOP_K
    q_emb = embed_text(query)
    mongo_filter = {"subject_id": subject_id}
    if unit is not None:
        mongo_filter["$or"] = [{"unit": unit}, {"unit": None}]
    if doc_types:
        mongo_filter["doc_type"] = {"$in": doc_types}

    scored = []
    for row in db.chunks().find(mongo_filter):
        score = cosine(q_emb, row["embedding"])
        # prefer chunks explicitly tagged with the requested unit
        if unit is not None and row.get("unit") == unit:
            score += 0.05
        scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, row in scored[:top_k]:
        results.append(
            {
                "text": row["text"],
                "unit": row.get("unit"),
                "doc_type": row.get("doc_type"),
                "score": round(score, 4),
                "document_id": row.get("document_id"),
            }
        )
    return results


def build_context(passages: list[dict], max_chars: int = 4000) -> str:
    out, total = [], 0
    for i, p in enumerate(passages, 1):
        block = f"[Source {i} | {p.get('doc_type')} | unit {p.get('unit')}]\n{p['text']}"
        if total + len(block) > max_chars:
            break
        out.append(block)
        total += len(block)
    return "\n\n".join(out)


# ---------------- Duplicate detection ----------------
def is_duplicate(subject_id: str, question_text: str, extra_pool: list[str] | None = None):
    """Return (is_dup, best_score, matched_question)."""
    q_emb = embed_text(question_text)
    best_score, matched = 0.0, None

    for row in db.question_bank().find({"subject_id": subject_id}, {"question": 1, "embedding": 1}):
        emb = row.get("embedding")
        if not emb:
            continue
        s = cosine(q_emb, emb)
        if s > best_score:
            best_score, matched = s, row["question"]

    for prev in extra_pool or []:
        s = cosine(q_emb, embed_text(prev))
        if s > best_score:
            best_score, matched = s, prev

    return best_score >= config.DUPLICATE_THRESHOLD, round(best_score, 4), matched


def hallucination_score(question_text: str, context: str) -> float:
    """Fraction of content words in the question that also appear in the retrieved
    context. Low overlap => likely unsupported / hallucinated.
    """
    stop = set(
        "the a an of to in and or is are for with on by as be that this what which "
        "explain describe discuss define list state write give how why when where".split()
    )
    q_words = {w for w in re.findall(r"[a-z]{3,}", question_text.lower()) if w not in stop}
    if not q_words:
        return 1.0
    ctx_words = set(re.findall(r"[a-z]{3,}", context.lower()))
    overlap = len(q_words & ctx_words) / len(q_words)
    return round(overlap, 3)
