"""MongoDB connection and collection accessors + index setup."""
from datetime import datetime, timezone

from pymongo import ASCENDING, MongoClient, TEXT

from config import config

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_db():
    return get_client()[config.MONGO_DB_NAME]


# --- Collection shortcuts ---
def users():
    return get_db()["users"]


def subjects():
    return get_db()["subjects"]


def documents():
    return get_db()["documents"]


def chunks():
    return get_db()["chunks"]  # RAG vector store


def question_bank():
    return get_db()["question_bank"]


def question_papers():
    return get_db()["question_papers"]


def generated_questions():
    return get_db()["generated_questions"]


def answers():
    return get_db()["answers"]


def exam_patterns():
    return get_db()["exam_patterns"]


def audit_logs():
    return get_db()["audit_logs"]


def utcnow():
    return datetime.now(timezone.utc)


def ensure_indexes():
    users().create_index([("email", ASCENDING)], unique=True)
    subjects().create_index([("code", ASCENDING)], unique=True)
    documents().create_index([("subject_id", ASCENDING), ("type", ASCENDING)])
    chunks().create_index([("subject_id", ASCENDING)])
    question_bank().create_index([("subject_id", ASCENDING), ("unit", ASCENDING)])
    question_bank().create_index([("question", TEXT)])
    question_papers().create_index([("created_by", ASCENDING)])
    audit_logs().create_index([("timestamp", ASCENDING)])
