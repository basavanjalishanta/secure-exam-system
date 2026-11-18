"""Flask application entry point."""
import os

from flask import Flask, jsonify
from flask_cors import CORS

from config import config
from models import db
from services.ai_service import AIProviderError


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_MB * 1024 * 1024

    CORS(
        app,
        resources={r"/api/*": {"origins": os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")}},
        supports_credentials=True,
    )

    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    os.makedirs(config.ENCRYPTED_DIR, exist_ok=True)

    # --- blueprints ---
    from routes.answers import bp as answers_bp
    from routes.auth import bp as auth_bp
    from routes.documents import bp as documents_bp
    from routes.misc import bp as misc_bp
    from routes.papers import bp as papers_bp
    from routes.pattern import bp as pattern_bp
    from routes.question_bank import bp as qbank_bp
    from routes.questions import bp as questions_bp
    from routes.subjects import bp as subjects_bp
    from routes.users import bp as users_bp
    from routes.validation import bp as validation_bp
    from routes.lesson_plans import bp as lesson_plans_bp

    for bp in (auth_bp, users_bp, subjects_bp, documents_bp, pattern_bp, questions_bp,
               answers_bp, validation_bp, papers_bp, qbank_bp, misc_bp, lesson_plans_bp):
        app.register_blueprint(bp)

    @app.get("/api/health")
    def health():
        try:
            db.get_client().admin.command("ping")
            mongo_ok = True
        except Exception:  # noqa: BLE001
            mongo_ok = False
        return jsonify({"status": "ok", "mongo": mongo_ok, "ai_provider": config.AI_PROVIDER})

    @app.errorhandler(413)
    def too_large(_):
        return jsonify({"error": "File too large"}), 413

    @app.errorhandler(AIProviderError)
    def ai_provider_error(exc):
        return jsonify({"error": str(exc)}), 503

    @app.errorhandler(500)
    def server_error(exc):
        return jsonify({"error": "Internal server error", "detail": str(exc)}), 500

    try:
        db.ensure_indexes()
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("Could not create indexes (is MongoDB running?): %s", exc)

    return app


app = create_app()

if __name__ == "__main__":
    # threaded=True: question generation can run for minutes against a local
    # LLM - without this, that one request blocks every other page/request.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=config.DEBUG, threaded=True)
