"""Central configuration. All secrets come from environment variables (.env)."""
import os
from datetime import timedelta

from dotenv import load_dotenv

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

    # --- AI provider abstraction ---
    # AI_PROVIDER = "mock" (dev/testing) | "llama" (local LLaMA-compatible endpoint)
    AI_PROVIDER = _get("AI_PROVIDER", "mock")
    LLAMA_BASE_URL = _get("LLAMA_BASE_URL", "http://localhost:11434/v1")
    LLAMA_API_KEY = _get("LLAMA_API_KEY", "not-needed-for-local")
    LLAMA_MODEL = _get("LLAMA_MODEL", "llama3")
    LLAMA_TIMEOUT = int(_get("LLAMA_TIMEOUT", "120"))
    # How many pattern slots to generate concurrently against the local LLM.
    # Ollama can genuinely overlap several requests on one GPU/model; tune
    # this down on weaker hardware if generations start failing/timing out.
    LLM_CONCURRENCY = int(_get("LLM_CONCURRENCY", "4"))

    # --- Embeddings abstraction ---
    # EMBEDDING_PROVIDER = "hash" (deterministic local fallback, no deps)
    #                    | "sentence-transformers" (local model)
    #                    | "llama" (embeddings endpoint of the local server)
    EMBEDDING_PROVIDER = _get("EMBEDDING_PROVIDER", "hash")
    EMBEDDING_MODEL = _get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_DIM = int(_get("EMBEDDING_DIM", "384"))

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
