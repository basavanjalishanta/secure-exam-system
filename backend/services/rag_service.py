"""Retrieval-Augmented Generation pipeline.

- Embedding provider abstraction (hash fallback / sentence-transformers / llama)
- Vector store backed by MongoDB `chunks` collection
- Cosine similarity retrieval computed locally with numpy
- Semantic similarity used for duplicate detection

No uploaded examination material ever leaves this machine.
"""
import hashlib
import logging
import math
import re
import threading
from collections import OrderedDict

import numpy as np

from config import config
from models import db
from services.ai_service import AIProviderError

_ST_MODEL = None
logger = logging.getLogger(__name__)
_EMBEDDING_CACHE_LIMIT = 4096
_EMBEDDING_CACHE: OrderedDict[tuple[str, str, int, str], tuple[float, ...]] = OrderedDict()
_EMBEDDING_CACHE_LOCK = threading.Lock()
_MISSING_DOC_INDEX_LOCK = threading.Lock()


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


_LLAMA_CLIENT = None


def _get_llama_client():
    global _LLAMA_CLIENT
    if _LLAMA_CLIENT is None:
        from openai import OpenAI

        _LLAMA_CLIENT = OpenAI(
            base_url=config.LLAMA_BASE_URL,
            api_key=config.LLAMA_API_KEY,
            timeout=config.LLAMA_TIMEOUT,
        )
    return _LLAMA_CLIENT


def _llama_embedding(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    try:
        client = _get_llama_client()
        resp = client.embeddings.create(model=config.EMBEDDING_MODEL, input=texts)
    except Exception as exc:
        logger.exception("Ollama embedding request failed")
        raise AIProviderError(
            "Could not reach Ollama embeddings. Confirm the server is running, the "
            "embedding model is installed, and OLLAMA_BASE_URL is correct."
        ) from exc
    return [d.embedding for d in resp.data]


def _compute_embeddings(texts: list[str]) -> list[list[float]]:
    provider = config.EMBEDDING_PROVIDER
    if provider == "sentence-transformers":
        return _sentence_transformer_embedding(texts)
    if provider == "llama":
        return _llama_embedding(texts)
    return [_hash_embedding(t, config.EMBEDDING_DIM) for t in texts]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    provider = config.EMBEDDING_PROVIDER
    model = config.EMBEDDING_MODEL
    dimension = config.EMBEDDING_DIM
    keys = [(provider, model, dimension, text) for text in texts]

    with _EMBEDDING_CACHE_LOCK:
        missing = []
        seen = set()
        for key in keys:
            if key in _EMBEDDING_CACHE:
                _EMBEDDING_CACHE.move_to_end(key)
            elif key not in seen:
                missing.append(key[3])
                seen.add(key)

    if missing:
        vectors = _compute_embeddings(missing)
        if len(vectors) != len(missing):
            raise AIProviderError("The embedding provider returned an incomplete result.")
        with _EMBEDDING_CACHE_LOCK:
            for text, vector in zip(missing, vectors):
                key = (provider, model, dimension, text)
                _EMBEDDING_CACHE[key] = tuple(float(value) for value in vector)
                _EMBEDDING_CACHE.move_to_end(key)
            while len(_EMBEDDING_CACHE) > _EMBEDDING_CACHE_LIMIT:
                _EMBEDDING_CACHE.popitem(last=False)

    with _EMBEDDING_CACHE_LOCK:
        for key in keys:
            _EMBEDDING_CACHE.move_to_end(key)
        return [list(_EMBEDDING_CACHE[key]) for key in keys]


def _embedding_dimension(embedding) -> int | None:
    if embedding is None:
        return None
    try:
        vector = np.asarray(embedding, dtype=np.float32)
    except (TypeError, ValueError):
        return None
    return int(vector.shape[0]) if vector.ndim == 1 else None


def _repair_stored_embeddings(collection, rows: list[dict], text_field: str, expected_dim: int):
    stale_rows = []
    for row in rows:
        if _embedding_dimension(row.get("embedding")) == expected_dim:
            continue
        text = row.get(text_field)
        if isinstance(text, str) and text.strip():
            stale_rows.append(row)
        else:
            row["embedding"] = None

    if not stale_rows:
        return

    vectors = embed_texts([row[text_field] for row in stale_rows])
    for row, vector in zip(stale_rows, vectors):
        actual_dim = _embedding_dimension(vector)
        if actual_dim != expected_dim:
            raise AIProviderError(
                f"The embedding provider returned {actual_dim or 'invalid'} dimensions; "
                f"{expected_dim} were expected."
            )
        row["embedding"] = vector
        if row.get("_id") is not None:
            collection.update_one(
                {"_id": row["_id"]},
                {"$set": {"embedding": vector}},
            )


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


# ---------------- Similarity ----------------
def cosine(a, b) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    if a.ndim != 1 or b.ndim != 1 or a.shape != b.shape:
        raise ValueError(f"Embedding dimensions do not match: {a.shape} and {b.shape}.")
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


def _ensure_subject_chunks(subject_id: str, doc_types: list[str] | None = None):
    with _MISSING_DOC_INDEX_LOCK:
        chunks_collection = db.chunks()
        indexed_ids = {
            str(document_id)
            for document_id in chunks_collection.distinct(
                "document_id", {"subject_id": subject_id}
            )
            if document_id is not None
        }
        document_filter = {"subject_id": subject_id}
        if doc_types:
            document_filter["type"] = {"$in": doc_types}
        documents = db.documents().find(document_filter)

        from services import document_service

        for document in documents:
            document_id = str(document.get("_id") or "")
            text = document.get("extracted_text")
            if not document_id or document_id in indexed_ids:
                continue
            if not isinstance(text, str) or not text.strip():
                continue

            chunks = document_service.chunk_text(text)
            if chunks:
                index_chunks(
                    subject_id,
                    document_id,
                    document.get("type", "notes"),
                    chunks,
                )
                indexed_ids.add(document_id)


def retrieve(subject_id: str, query: str, unit: int | None = None, top_k: int | None = None,
             doc_types: list[str] | None = None) -> list[dict]:
    top_k = top_k or config.RAG_TOP_K
    q_emb = embed_text(query)
    mongo_filter = {"subject_id": subject_id}
    if unit is not None:
        mongo_filter["$or"] = [{"unit": unit}, {"unit": None}]
    if doc_types:
        mongo_filter["doc_type"] = {"$in": doc_types}

    _ensure_subject_chunks(subject_id, doc_types)
    collection = db.chunks()
    rows = list(collection.find(mongo_filter))
    _repair_stored_embeddings(collection, rows, "text", len(q_emb))

    scored = []
    for row in rows:
        if _embedding_dimension(row.get("embedding")) != len(q_emb):
            continue
        score = cosine(q_emb, row["embedding"])
        # prefer chunks explicitly tagged with the requested unit
        if unit is not None and row.get("unit") == unit:
            score += 0.05
        scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    seen_text = set()
    for score, row in scored:
        normalized_text = re.sub(r"\s+", " ", row["text"]).strip().casefold()
        if not normalized_text or normalized_text in seen_text:
            continue
        seen_text.add(normalized_text)
        results.append(
            {
                "text": row["text"],
                "unit": row.get("unit"),
                "doc_type": row.get("doc_type"),
                "score": round(score, 4),
                "document_id": row.get("document_id"),
            }
        )
        if len(results) >= top_k:
            break
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

    collection = db.question_bank()
    rows = list(collection.find({"subject_id": subject_id}, {"question": 1, "embedding": 1}))
    _repair_stored_embeddings(collection, rows, "question", len(q_emb))

    for row in rows:
        emb = row.get("embedding")
        if _embedding_dimension(emb) != len(q_emb):
            continue
        s = cosine(q_emb, emb)
        if s > best_score:
            best_score, matched = s, row["question"]

    if extra_pool:
        extra_embs = embed_texts(extra_pool)
        for prev, emb in zip(extra_pool, extra_embs):
            s = cosine(q_emb, emb)
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
