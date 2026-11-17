"""Lesson Plan Management & Export endpoints."""
import io
from bson import ObjectId
from flask import Blueprint, g, jsonify, request, send_file

from models import db
from services import lesson_plan_service
from utils.audit import log_action
from utils.security import lecturer_required
from utils.serialization import jsonify_doc

bp = Blueprint("lesson_plans", __name__, url_prefix="/api/lesson-plans")


@bp.post("/generate")
@lecturer_required
def generate():
    data = request.get_json(force=True) or {}
    subject_id = data.get("subject_id")
    if not subject_id:
        return jsonify({"error": "subject_id is required"}), 400

    try:
        plan = lesson_plan_service.generate_lesson_plan(subject_id, meta=data.get("meta"))
        log_action("GENERATE_LESSON_PLAN", subject_id=subject_id, contact_hours=plan.get("total_contact_hours"))
        return jsonify({"lesson_plan": jsonify_doc(plan)}), 200
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 404
    except Exception as exc:
        return jsonify({"error": f"Failed to generate lesson plan: {exc}"}), 500


@bp.get("/subject/<subject_id>")
@lecturer_required
def get_by_subject(subject_id):
    plan = db.lesson_plans().find_one({"subject_id": subject_id})
    if not plan:
        return jsonify({"lesson_plan": None}), 200
    return jsonify({"lesson_plan": jsonify_doc(plan)}), 200


@bp.put("/<plan_id>")
@lecturer_required
def update_plan(plan_id):
    data = request.get_json(force=True) or {}
    plan = db.lesson_plans().find_one({"_id": ObjectId(plan_id)})
    if not plan:
        return jsonify({"error": "Lesson plan not found"}), 404

    # Allow editing metadata and lecture schedule
    allowed = ["faculty_name", "designation", "total_contact_hours", "section", "lecture_schedule",
               "course_objectives", "prerequisites", "course_outcomes", "textbooks", "references"]
    update_data = {k: data[k] for k in allowed if k in data}
    update_data["updated_at"] = db.utcnow()

    db.lesson_plans().update_one({"_id": ObjectId(plan_id)}, {"$set": update_data})
    updated = db.lesson_plans().find_one({"_id": ObjectId(plan_id)})
    log_action("UPDATE_LESSON_PLAN", plan_id=plan_id, subject_id=str(plan["subject_id"]))
    return jsonify({"lesson_plan": jsonify_doc(updated)}), 200


@bp.post("/<plan_id>/approve")
@lecturer_required
def approve_plan(plan_id):
    plan = db.lesson_plans().find_one({"_id": ObjectId(plan_id)})
    if not plan:
        return jsonify({"error": "Lesson plan not found"}), 404

    db.lesson_plans().update_one(
        {"_id": ObjectId(plan_id)},
        {"$set": {"approved": True, "approved_by": str(g.current_user["_id"]), "approved_at": db.utcnow()}},
    )
    log_action("APPROVE_LESSON_PLAN", plan_id=plan_id, subject_id=str(plan["subject_id"]))
    return jsonify({"message": "Lesson plan successfully approved"}), 200


@bp.get("/<plan_id>/export-pdf")
@lecturer_required
def export_pdf(plan_id):
    plan = db.lesson_plans().find_one({"_id": ObjectId(plan_id)})
    if not plan:
        return jsonify({"error": "Lesson plan not found"}), 404

    pdf_bytes = lesson_plan_service.build_lesson_plan_pdf(plan)
    code = plan.get("course_code", "Course")
    filename = f"Course_Plan_{code}.pdf"
    log_action("EXPORT_LESSON_PLAN_PDF", plan_id=plan_id, filename=filename)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
