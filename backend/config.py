"""Central configuration. All secrets come from environment variables (.env)."""
import os
from datetime import timedelta

from dotenv import load_dotenv

backend_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(backend_env):
    load_dotenv(backend_env, override=True)
else:
    load_dotenv()


def _get(key: str, default=None, required: bool = False):
    val = os.environ.get(key, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


class Config:
    # --- Flask ---
    SECRET_KEY = _get("FLASK_SECRET_KEY", "dev-only-change-me")
    DEBUG = _get("FLASK_DEBUG", "false").lower() == "true"

    # --- Mongo ---
    MONGO_URI = _get("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = _get("MONGO_DB_NAME", "secure_exam_system")

    # --- JWT ---
    JWT_SECRET = _get("JWT_SECRET", "dev-jwt-secret-change-me")
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TTL = timedelta(hours=int(_get("JWT_ACCESS_TTL_HOURS", "12")))

    # --- Email-based second factor (Gmail App Password / SMTP) ---
    SMTP_HOST = _get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(_get("SMTP_PORT", "465"))
    SMTP_USERNAME = _get("SMTP_USERNAME", "")
    SMTP_PASSWORD = _get("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = _get("SMTP_FROM_EMAIL", "") or SMTP_USERNAME
    EMAIL_OTP_TTL_MINUTES = int(_get("EMAIL_OTP_TTL_MINUTES", "5"))

    # --- AES-256 encryption for generated papers ---
    # 32-byte key, provided base64 or hex encoded in the env.
    AES_KEY_B64 = _get("AES_KEY_B64", "")
    AES_KEY_HEX = _get("AES_KEY_HEX", "")

    # --- File uploads ---
    UPLOAD_DIR = _get("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "uploads"))
    ENCRYPTED_DIR = _get(
        "ENCRYPTED_DIR", os.path.join(os.path.dirname(__file__), "encrypted_papers")
    )
    MAX_CONTENT_MB = int(_get("MAX_CONTENT_MB", "40"))
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

    # --- Local AI provider ---
    # AI_PROVIDER = "ollama" | "mock" (development/testing only)
    AI_PROVIDER = _get("AI_PROVIDER", "ollama").lower()

    # OLLAMA_* names are preferred; LLAMA_* remain supported for existing setups.
    OLLAMA_BASE_URL = _get(
        "OLLAMA_BASE_URL",
        _get("LLAMA_BASE_URL", "http://localhost:11434/v1"),
    )
    OLLAMA_API_KEY = _get("OLLAMA_API_KEY", _get("LLAMA_API_KEY", "ollama"))
    OLLAMA_MODEL = _get("OLLAMA_MODEL", _get("LLAMA_MODEL", "qwen2.5:3b"))
    OLLAMA_TIMEOUT = int(_get("OLLAMA_TIMEOUT", _get("LLAMA_TIMEOUT", "180")))
    OLLAMA_TEMPERATURE = float(
        _get("OLLAMA_TEMPERATURE", _get("LLAMA_TEMPERATURE", "0.2"))
    )
    # Compatibility aliases for the existing embedding/RAG integration.
    LLAMA_BASE_URL = OLLAMA_BASE_URL
    LLAMA_API_KEY = OLLAMA_API_KEY
    LLAMA_MODEL = OLLAMA_MODEL
    LLAMA_TIMEOUT = OLLAMA_TIMEOUT
    LLM_CONCURRENCY = int(_get("LLM_CONCURRENCY", "1"))
    # EMBEDDING_PROVIDER = "hash" (deterministic local fallback, no deps)
    #                    | "sentence-transformers" (local model)
    #                    | "llama" (embeddings endpoint of the local server)
    EMBEDDING_PROVIDER = _get("EMBEDDING_PROVIDER", "llama")
    EMBEDDING_MODEL = _get("EMBEDDING_MODEL", "nomic-embed-text")
    EMBEDDING_DIM = int(_get("EMBEDDING_DIM", "768"))

    # --- RAG ---
    CHUNK_SIZE = int(_get("CHUNK_SIZE", "900"))
    CHUNK_OVERLAP = int(_get("CHUNK_OVERLAP", "150"))
    RAG_TOP_K = int(_get("RAG_TOP_K", "6"))

    # --- Duplicate detection ---
    DUPLICATE_THRESHOLD = float(_get("DUPLICATE_THRESHOLD", "0.86"))

    @staticmethod
    def aes_key() -> bytes:
        import base64

        if Config.AES_KEY_B64:
            key = base64.b64decode(Config.AES_KEY_B64)
        elif Config.AES_KEY_HEX:
            key = bytes.fromhex(Config.AES_KEY_HEX)
        else:
            # Dev fallback ONLY. Real deployments must set AES_KEY_B64/HEX.
            key = b"dev-insecure-aes-key-not-for-prod-32b"[:32].ljust(32, b"0")
        if len(key) != 32:
            raise RuntimeError("AES key must be exactly 32 bytes for AES-256")
        return key


config = Config()
