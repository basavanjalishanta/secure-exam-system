"""Audit logs + dashboard stats."""
from flask import Blueprint, g, jsonify, request

from models import db
from utils.security import admin_required, jwt_required
from utils.serialization import jsonify_doc

bp = Blueprint("misc", __name__, url_prefix="/api")


@bp.get("/audit-logs")
@admin_required
def audit_logs():
    limit = min(int(request.args.get("limit", 200)), 1000)
    action = request.args.get("action")
    q = {"action": action} if action else {}
    rows = list(db.audit_logs().find(q).sort("timestamp", -1).limit(limit))
    return jsonify({"logs": jsonify_doc(rows)})


@bp.get("/dashboard/stats")
@jwt_required
def dashboard_stats():
    is_admin = g.current_user["role"] == "admin"
    paper_filter = {} if is_admin else {"created_by": str(g.current_user["_id"])}
    stats = {
        "total_subjects": db.subjects().count_documents({}),
        "total_questions": db.question_bank().count_documents({}),
        "generated_papers": db.question_papers().count_documents(paper_filter),
        "uploaded_documents": db.documents().count_documents({}),
    }

    # distributions
    def _dist(field):
        pipeline = [{"$group": {"_id": f"${field}", "count": {"$sum": 1}}}]
        return {str(r["_id"]): r["count"] for r in db.question_bank().aggregate(pipeline)}

    difficulty = _dist("difficulty")
    units = _dist("unit")
    qtypes = _dist("question_type")

    recent_activity = jsonify_doc(
        list(db.audit_logs().find({} if is_admin else {"user_id": str(g.current_user["_id"])})
             .sort("timestamp", -1).limit(15))
    )
    generation_history = jsonify_doc(
        list(db.generated_questions().find(
            {} if is_admin else {"created_by": str(g.current_user["_id"])}
        ).sort("created_at", -1).limit(10))
    )
    for gh in generation_history:
        gh.pop("questions", None)

    return jsonify(
        {
            "stats": stats,
            "difficulty_distribution": difficulty,
            "unit_coverage": units,
            "question_type_distribution": qtypes,
            "recent_activity": recent_activity,
            "generation_history": generation_history,
        }
    )
