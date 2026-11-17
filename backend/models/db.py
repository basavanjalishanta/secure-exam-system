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


def generation_jobs():
    return get_db()["generation_jobs"]


def lesson_plans():
    return get_db()["lesson_plans"]


def answers():
    return get_db()["answers"]


def exam_patterns():
    return get_db()["exam_patterns"]


def audit_logs():
    return get_db()["audit_logs"]


def utcnow():
    return datetime.now(timezone.utc)


def ensure_indexes():
    indexes = [
        (users(), [("email", ASCENDING)], {"unique": True}),
        (subjects(), [("code", ASCENDING)], {"unique": True}),
        (documents(), [("subject_id", ASCENDING), ("type", ASCENDING)], {}),
        (chunks(), [("subject_id", ASCENDING)], {}),
        (question_bank(), [("subject_id", ASCENDING), ("unit", ASCENDING)], {}),
        (question_bank(), [("question", TEXT)], {}),
        (question_papers(), [("created_by", ASCENDING)], {}),
        (audit_logs(), [("timestamp", ASCENDING)], {}),
        (generation_jobs(), [("job_id", ASCENDING)], {"unique": True}),
        (generation_jobs(), [("subject_id", ASCENDING), ("status", ASCENDING)], {}),
        (lesson_plans(), [("subject_id", ASCENDING)], {}),
    ]
    for coll, keys, kwargs in indexes:
        try:
            coll.create_index(keys, **kwargs)
        except Exception as e:
            print(f"Warning: Could not create index on {coll.name}: {e}")
