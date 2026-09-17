"""Seed the database with a ready-to-demo dataset.

Creates:
  * one admin + one lecturer account (passwords are taken from the environment,
    or randomly generated and printed ONCE - never committed)
  * the subject "Database Management Systems" (BCS401) with 5 units
  * syllabus / textbook / notes / 2 previous question papers (from backend/data/)
  * pattern analysis + a selected exam pattern

Usage:
    python seed.py            # create if missing
    python seed.py --reset    # drop all collections first
"""
import os
import secrets
import string
import sys

from config import config
from models import db
from services import document_service, pattern_service, rag_service
from utils.security import hash_password

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

DOCS = [
    ("syllabus", "dbms_syllabus.txt"),
    ("textbook", "dbms_textbook_notes.txt"),
    ("notes", "dbms_textbook_notes.txt"),
    ("previous_paper", "dbms_prev_paper_2023.txt"),
    ("previous_paper", "dbms_prev_paper_2022.txt"),
]

UNITS = [
    {"unit": 1, "title": "Introduction"},
    {"unit": 2, "title": "ER Model"},
    {"unit": 3, "title": "SQL"},
    {"unit": 4, "title": "Normalization"},
    {"unit": 5, "title": "Transactions"},
]


def _rand_password(n=16):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def reset():
    for name in ("users", "subjects", "documents", "chunks", "question_bank",
                 "question_papers", "generated_questions", "answers",
                 "exam_patterns", "audit_logs"):
        db.get_db()[name].drop()
    print("Dropped all collections.")


def seed_users():
    created = {}
    for role, email_env, pass_env, default_email in (
        ("admin", "SEED_ADMIN_EMAIL", "SEED_ADMIN_PASSWORD", "admin@example.edu"),
        ("lecturer", "SEED_LECTURER_EMAIL", "SEED_LECTURER_PASSWORD", "lecturer@example.edu"),
    ):
        email = os.environ.get(email_env, default_email).lower()
        if db.users().find_one({"email": email}):
            print(f"  user {email} already exists, skipping")
            continue
        password = os.environ.get(pass_env) or _rand_password()
        db.users().insert_one(
            {
                "name": role.capitalize() + " User",
                "email": email,
                "password_hash": hash_password(password),
                "role": role,
                "active": True,
                "created_at": db.utcnow(),
            }
        )
        created[email] = password
        print(f"  created {role}: {email}")
    if created:
        print("\n  >>> SAVE THESE CREDENTIALS (shown only once) <<<")
        for email, pw in created.items():
            print(f"      {email}  /  {pw}")
        print()


def seed_subject():
    existing = db.subjects().find_one({"code": "BCS401"})
    if existing:
        print("  subject BCS401 already exists")
        return existing
    doc = {
        "name": "Database Management Systems",
        "code": "BCS401",
        "semester": 6,
        "units": UNITS,
        "created_at": db.utcnow(),
    }
    res = db.subjects().insert_one(doc)
    doc["_id"] = res.inserted_id
    print("  created subject: Database Management Systems (BCS401)")
    return doc


def seed_documents(subject):
    subject_id = str(subject["_id"])
    if db.documents().count_documents({"subject_id": subject_id}):
        print("  documents already present, skipping ingestion")
        return
    unit_nums = [u["unit"] for u in UNITS]
    for doc_type, fname in DOCS:
        path = os.path.join(DATA_DIR, fname)
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
        cleaned = document_service.clean_text(raw)
        d = {
            "subject_id": subject_id,
            "type": doc_type,
            "filename": fname,
            "extracted_text": cleaned,
            "char_count": len(cleaned),
            "detected_units": document_service.detect_units(cleaned),
            "uploaded_by": "seed",
            "created_at": db.utcnow(),
        }
        res = db.documents().insert_one(d)
        chunks = document_service.chunk_text(cleaned, unit_nums)
        n = rag_service.index_chunks(subject_id, str(res.inserted_id), doc_type, chunks)
        print(f"  ingested {fname} as {doc_type}: {n} chunks indexed")


def seed_pattern(subject):
    subject_id = str(subject["_id"])
    texts = [d["extracted_text"] for d in db.documents().find(
        {"subject_id": subject_id, "type": "previous_paper"})]
    analysis = pattern_service.analyze_papers(texts)
    pattern = analysis.get("suggested_pattern") or pattern_service.default_patterns()[0]
    pattern.setdefault("total_marks", sum(s["total"] for s in pattern["sections"]))
    db.subjects().update_one(
        {"_id": subject["_id"]},
        {"$set": {"pattern_analysis": analysis, "selected_pattern": pattern,
                  "pattern_mode": "auto"}},
    )
    print(f"  pattern analyzed ({analysis.get('questions_found')} questions) "
          f"-> selected '{pattern['name']}' ({pattern['total_marks']} marks)")


def main():
    if "--reset" in sys.argv:
        reset()
    db.ensure_indexes()
    print(f"Seeding database '{config.MONGO_DB_NAME}' (AI provider: {config.AI_PROVIDER})")
    seed_users()
    subject = seed_subject()
    seed_documents(subject)
    seed_pattern(subject)
    print("\nDone. Start the backend with:  flask --app app run  (or python app.py)")


if __name__ == "__main__":
    main()
