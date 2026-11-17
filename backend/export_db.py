"""Export database collections and uploaded files to backend/data/seed_dump/

This snapshot can be reloaded automatically during database seeding.
"""
import os
import shutil
from bson import json_util
from models import db

DUMP_DIR = os.path.join(os.path.dirname(__file__), "data", "seed_dump")
COLLECTIONS_DIR = os.path.join(DUMP_DIR, "collections")
UPLOADS_DUMP_DIR = os.path.join(DUMP_DIR, "uploads")
ENCRYPTED_DUMP_DIR = os.path.join(DUMP_DIR, "encrypted_papers")

UPLOADS_SRC = os.path.join(os.path.dirname(__file__), "uploads")
ENCRYPTED_SRC = os.path.join(os.path.dirname(__file__), "encrypted_papers")

COLLECTION_NAMES = (
    "users",
    "subjects",
    "documents",
    "chunks",
    "question_bank",
    "question_papers",
    "generated_questions",
    "answers",
    "exam_patterns",
    "audit_logs",
)


def export_all():
    os.makedirs(COLLECTIONS_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DUMP_DIR, exist_ok=True)
    os.makedirs(ENCRYPTED_DUMP_DIR, exist_ok=True)

    db_obj = db.get_db()
    print(f"Exporting database collections to {COLLECTIONS_DIR}...")

    total_docs = 0
    for name in COLLECTION_NAMES:
        docs = list(db_obj[name].find())
        json_path = os.path.join(COLLECTIONS_DIR, f"{name}.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            fh.write(json_util.dumps(docs, indent=2))
        print(f"  * {name}: {len(docs)} documents exported")
        total_docs += len(docs)

    # Copy upload files
    file_count = 0
    if os.path.exists(UPLOADS_SRC):
        for fname in os.listdir(UPLOADS_SRC):
            if fname == ".gitkeep":
                continue
            src_file = os.path.join(UPLOADS_SRC, fname)
            if os.path.isfile(src_file):
                shutil.copy2(src_file, os.path.join(UPLOADS_DUMP_DIR, fname))
                file_count += 1
    print(f"  * Uploaded files: {file_count} files backed up")

    # Copy encrypted papers
    enc_count = 0
    if os.path.exists(ENCRYPTED_SRC):
        for fname in os.listdir(ENCRYPTED_SRC):
            if fname == ".gitkeep":
                continue
            src_file = os.path.join(ENCRYPTED_SRC, fname)
            if os.path.isfile(src_file):
                shutil.copy2(src_file, os.path.join(ENCRYPTED_DUMP_DIR, fname))
                enc_count += 1
    print(f"  * Encrypted paper files: {enc_count} files backed up")

    print(f"\nSnapshot export complete! Total documents: {total_docs}, Files: {file_count + enc_count}")


if __name__ == "__main__":
    export_all()
