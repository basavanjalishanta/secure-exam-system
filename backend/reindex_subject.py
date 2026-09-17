"""Re-extract + re-clean + re-chunk + re-index every uploaded file still on
disk for a subject, using the current document_service pipeline.

Use this after a document_service/pipeline fix or config change instead of
re-uploading through the browser, as long as the original files are still in
backend/uploads/. It clears any existing chunks for the subject first.

Usage:
    python reindex_subject.py <subject_id>
"""
import os
import sys

from bson import ObjectId

from config import config
from models import db
from services import document_service, rag_service

VALID_TYPES = ["previous_paper", "syllabus", "textbook", "notes"]  # longest-prefix first


def main(subject_id: str):
    subject = db.subjects().find_one({"_id": ObjectId(subject_id)})
    if not subject:
        print("subject not found")
        sys.exit(1)

    prefix = f"{subject_id}_"
    files = [f for f in os.listdir(config.UPLOAD_DIR) if f.startswith(prefix)]
    if not files:
        print("no uploaded files found on disk for this subject")
        sys.exit(1)

    cleared_docs = db.documents().delete_many({"subject_id": subject_id})
    cleared_chunks = db.chunks().delete_many({"subject_id": subject_id})
    print(f"cleared {cleared_docs.deleted_count} documents, {cleared_chunks.deleted_count} chunks")

    unit_nums = [u["unit"] for u in subject.get("units", [])]

    for stored_name in sorted(files):
        # stored as: {subject_id}_{type}_{timestamp}_{original filename}
        rest = stored_name[len(prefix):]
        doc_type = next((t for t in VALID_TYPES if rest.startswith(t + "_")), None)
        if doc_type is None:
            print(f"SKIP {stored_name}: unrecognized type prefix")
            continue
        remainder = rest[len(doc_type) + 1 :]
        _, _, original_name = remainder.partition("_")

        path = os.path.join(config.UPLOAD_DIR, stored_name)
        with open(path, "rb") as fh:
            raw = fh.read()

        try:
            text = document_service.extract_text(original_name, raw)
        except Exception as exc:  # noqa: BLE001
            print(f"SKIP {stored_name}: {exc}")
            continue
        cleaned = document_service.clean_text(text)

        doc = {
            "subject_id": subject_id,
            "type": doc_type,
            "filename": original_name,
            "stored_name": stored_name,
            "extracted_text": cleaned,
            "char_count": len(cleaned),
            "detected_units": document_service.detect_units(cleaned),
            "uploaded_by": "reindex-script",
            "created_at": db.utcnow(),
        }
        res = db.documents().insert_one(doc)
        chunks = document_service.chunk_text(cleaned, unit_nums)
        n = rag_service.index_chunks(subject_id, str(res.inserted_id), doc_type, chunks)
        print(f"re-indexed {original_name} ({doc_type}): {n} chunks, {len(cleaned)} chars")

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
