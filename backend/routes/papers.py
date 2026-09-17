"""Question paper creation -> PDF -> AES-256 encryption -> secure storage/download.

The plaintext PDF is generated in memory, encrypted, and only the ciphertext is
persisted. Downloads are decrypted on the fly for authorized users only.
"""
import io

from bson import ObjectId
from flask import Blueprint, g, jsonify, request, send_file

from models import db
from services import encryption_service, pdf_service, rag_service
from utils.audit import log_action
from utils.security import jwt_required, lecturer_required
from utils.serialization import jsonify_doc

bp = Blueprint("papers", __name__, url_prefix="/api/papers")


def _can_access(paper: dict) -> bool:
    user = g.current_user
    if user["role"] == "admin":
        return True
    uid = str(user["_id"])
    if paper.get("created_by") == uid:
        return True
    return uid in paper.get("access_permissions", [])


def _store_questions_in_bank(subject_id: str, questions: list[dict]):
    stored = 0
    for q in questions:
        text = q.get("question", "")
        if not text:
            continue
        is_dup, score, _ = rag_service.is_duplicate(subject_id, text)
        if is_dup:
            db.question_bank().update_one(
                {"subject_id": subject_id, "question": text},
                {"$inc": {"usage_count": 1}},
            )
            continue
        db.question_bank().insert_one(
            {
                "subject_id": subject_id,
                "unit": q.get("unit"),
                "topic": q.get("topic"),
                "question": text,
                "answer": q.get("answer", ""),
                "marks": q.get("marks"),
                "difficulty": q.get("difficulty"),
                "bloom_level": q.get("bloom_level"),
                "question_type": q.get("question_type"),
                "source": q.get("source", []),
                "embedding": rag_service.embed_text(text),
                "usage_count": 1,
                "created_at": db.utcnow(),
            }
        )
        stored += 1
    return stored


@bp.post("/generate")
@lecturer_required
def generate_paper():
    data = request.get_json(force=True) or {}
    subject = db.subjects().find_one({"_id": ObjectId(data["subject_id"])}) if data.get("subject_id") else None
    if not subject:
        return jsonify({"error": "subject not found"}), 404
    questions = data.get("questions") or []
    if not questions:
        return jsonify({"error": "questions required"}), 400

    meta = data.get("meta") or {}
    meta.setdefault("college_name", "University College of Engineering")
    meta.setdefault("exam_name", "End Semester Examination")
    meta.setdefault("subject_name", subject["name"])
    meta.setdefault("subject_code", subject["code"])
    meta.setdefault("semester", subject.get("semester"))
    meta.setdefault("max_marks", sum(int(q.get("marks", 0)) for q in questions))

    paper_pdf = pdf_service.build_question_paper_pdf(meta, questions)
    answer_pdf = pdf_service.build_answer_key_pdf(meta, questions)

    paper_id = str(ObjectId())
    paper_meta = encryption_service.encrypt_file(paper_pdf, paper_id)
    answer_meta = encryption_service.encrypt_file(answer_pdf, paper_id + "_key")

    stored = _store_questions_in_bank(str(subject["_id"]), questions)

    doc = {
        "_id": ObjectId(paper_id),
        "subject_id": str(subject["_id"]),
        "subject_name": subject["name"],
        "pattern": data.get("pattern") or subject.get("selected_pattern"),
        "meta": meta,
        "question_count": len(questions),
        "total_marks": meta["max_marks"],
        "encrypted": True,
        "encryption": {"paper": paper_meta, "answer_key": answer_meta},
        "created_by": str(g.current_user["_id"]),
        "created_by_name": g.current_user["name"],
        "access_permissions": [str(g.current_user["_id"])],
        "created_at": db.utcnow(),
    }
    db.question_papers().insert_one(doc)
    log_action("GENERATE_PAPER", paper_id=paper_id, subject_id=str(subject["_id"]),
               total_marks=meta["max_marks"], questions_banked=stored)

    out = jsonify_doc(doc)
    out["encryption"] = {
        "paper": {"algorithm": paper_meta["algorithm"], "size_bytes": paper_meta["size_bytes"]},
        "answer_key": {"algorithm": answer_meta["algorithm"], "size_bytes": answer_meta["size_bytes"]},
    }
    out["questions_added_to_bank"] = stored
    return jsonify({"paper": out}), 201


@bp.post("/<paper_id>/encrypt")
@lecturer_required
def encrypt_status(paper_id):
    paper = db.question_papers().find_one({"_id": ObjectId(paper_id)})
    if not paper:
        return jsonify({"error": "not found"}), 404
    if not _can_access(paper):
        return jsonify({"error": "Access Denied"}), 403
    return jsonify(
        {
            "paper_id": paper_id,
            "encrypted": paper.get("encrypted", False),
            "algorithm": paper["encryption"]["paper"]["algorithm"],
            "plaintext_stored": False,
        }
    )


@bp.get("")
@jwt_required
def list_papers():
    q = {} if g.current_user["role"] == "admin" else {
        "$or": [
            {"created_by": str(g.current_user["_id"])},
            {"access_permissions": str(g.current_user["_id"])},
        ]
    }
    papers = list(db.question_papers().find(q).sort("created_at", -1))
    out = []
    for p in papers:
        j = jsonify_doc(p)
        j["encryption"] = {"algorithm": p["encryption"]["paper"]["algorithm"]}
        out.append(j)
    return jsonify({"papers": out})


@bp.get("/<paper_id>")
@jwt_required
def get_paper(paper_id):
    paper = db.question_papers().find_one({"_id": ObjectId(paper_id)})
    if not paper:
        return jsonify({"error": "not found"}), 404
    authorized = _can_access(paper)
    base = {
        "id": paper_id,
        "subject_name": paper.get("subject_name"),
        "total_marks": paper.get("total_marks"),
        "question_count": paper.get("question_count"),
        "encrypted": paper.get("encrypted"),
        "created_at": paper["created_at"].isoformat(),
        "authorized": authorized,
    }
    if not authorized:
        log_action("PAPER_ACCESS_DENIED", paper_id=paper_id)
        return jsonify({"paper": base, "message": "Access Denied"}), 403
    j = jsonify_doc(paper)
    j["encryption"] = {"algorithm": paper["encryption"]["paper"]["algorithm"]}
    j["authorized"] = True
    return jsonify({"paper": j})


@bp.post("/<paper_id>/share")
@lecturer_required
def share_paper(paper_id):
    paper = db.question_papers().find_one({"_id": ObjectId(paper_id)})
    if not paper or (paper.get("created_by") != str(g.current_user["_id"])
                     and g.current_user["role"] != "admin"):
        return jsonify({"error": "Access Denied"}), 403
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").lower()
    target = db.users().find_one({"email": email})
    if not target:
        return jsonify({"error": "user not found"}), 404
    db.question_papers().update_one(
        {"_id": ObjectId(paper_id)},
        {"$addToSet": {"access_permissions": str(target["_id"])}},
    )
    log_action("SHARE_PAPER", paper_id=paper_id, shared_with=email)
    return jsonify({"message": f"Access granted to {email}"})


@bp.get("/<paper_id>/download")
@jwt_required
def download(paper_id):
    kind = request.args.get("type", "paper")  # paper | answer_key
    paper = db.question_papers().find_one({"_id": ObjectId(paper_id)})
    if not paper:
        return jsonify({"error": "not found"}), 404
    if not _can_access(paper):
        log_action("PAPER_DOWNLOAD_DENIED", paper_id=paper_id, kind=kind)
        return jsonify({"error": "Access Denied"}), 403

    meta = paper["encryption"].get("answer_key" if kind == "answer_key" else "paper")
    try:
        plaintext = encryption_service.decrypt_file(meta)
    except Exception:  # noqa: BLE001
        return jsonify({"error": "decryption failed"}), 500

    log_action("DOWNLOAD_PAPER", paper_id=paper_id, kind=kind)
    filename = f"{paper.get('subject_name', 'paper')}_{kind}.pdf".replace(" ", "_")
    return send_file(
        io.BytesIO(plaintext),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
