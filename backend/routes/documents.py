"""Document upload + text extraction + RAG indexing."""
import os

from bson import ObjectId
from flask import Blueprint, g, jsonify, request
from werkzeug.utils import secure_filename

from config import config
from models import db
from services import document_service, rag_service
from utils.audit import log_action
from utils.security import lecturer_required
from utils.serialization import jsonify_doc

bp = Blueprint("documents", __name__, url_prefix="/api/documents")

VALID_TYPES = {"syllabus", "textbook", "notes", "previous_paper"}


@bp.post("/upload")
@lecturer_required
def upload():
    subject_id = request.form.get("subject_id")
    doc_type = request.form.get("type")
    file = request.files.get("file")

    if not subject_id or doc_type not in VALID_TYPES or not file:
        return jsonify({"error": "subject_id, valid type and file are required"}), 400
    subject = db.subjects().find_one({"_id": ObjectId(subject_id)})
    if not subject:
        return jsonify({"error": "subject not found"}), 404

    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        return jsonify({"error": f"file type {ext} not allowed"}), 400

    raw = file.read()
    if len(raw) > config.MAX_CONTENT_MB * 1024 * 1024:
        return jsonify({"error": "file too large"}), 413

    try:
        text = document_service.extract_text(filename, raw)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"could not extract text: {exc}"}), 422
    cleaned = document_service.clean_text(text)
    if len(cleaned) < 20:
        return jsonify({"error": "no readable text found in document"}), 422

    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    stored_name = f"{subject_id}_{doc_type}_{db.utcnow().timestamp():.0f}_{filename}"
    with open(os.path.join(config.UPLOAD_DIR, stored_name), "wb") as fh:
        fh.write(raw)

    units = [u["unit"] for u in subject.get("units", [])]
    detected_units = document_service.detect_units(cleaned)
    doc = {
        "subject_id": subject_id,
        "type": doc_type,
        "filename": filename,
        "stored_name": stored_name,
        "extracted_text": cleaned,
        "char_count": len(cleaned),
        "detected_units": detected_units,
        "uploaded_by": str(g.current_user["_id"]),
        "created_at": db.utcnow(),
    }
    res = db.documents().insert_one(doc)
    doc["_id"] = res.inserted_id

    chunks = document_service.chunk_text(cleaned, units)
    indexed = rag_service.index_chunks(subject_id, str(res.inserted_id), doc_type, chunks)

    log_action("UPLOAD_DOCUMENT", subject_id=subject_id, doc_type=doc_type,
               filename=filename, chunks=indexed)
    out = jsonify_doc(doc)
    out.pop("extracted_text", None)
    out["chunks_indexed"] = indexed
    out["preview"] = cleaned[:500]
    return jsonify({"document": out}), 201


@bp.get("/<subject_id>")
@lecturer_required
def list_by_subject(subject_id):
    docs = list(db.documents().find({"subject_id": subject_id}).sort("created_at", -1))
    out = []
    for d in docs:
        j = jsonify_doc(d)
        j.pop("extracted_text", None)
        j["preview"] = (d.get("extracted_text") or "")[:400]
        out.append(j)
    return jsonify({"documents": out})


@bp.delete("/<document_id>")
@lecturer_required
def delete_document(document_id):
    doc = db.documents().find_one({"_id": ObjectId(document_id)})
    if not doc:
        return jsonify({"error": "not found"}), 404
    db.documents().delete_one({"_id": ObjectId(document_id)})
    db.chunks().delete_many({"document_id": document_id})
    log_action("DELETE_DOCUMENT", document_id=document_id)
    return jsonify({"message": "deleted"})
