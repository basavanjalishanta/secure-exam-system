"""AES-256-GCM encryption for generated question papers.

The plaintext PDF is never stored on disk. Only the encrypted blob plus
metadata (nonce, tag, algorithm) is persisted.
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import config

ALGORITHM = "AES-256-GCM"


def encrypt_bytes(plaintext: bytes, associated_data: bytes | None = None) -> dict:
    key = config.aes_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
    return {
        "algorithm": ALGORITHM,
        "nonce_b64": base64.b64encode(nonce).decode(),
        "ciphertext": ciphertext,  # raw bytes; caller writes to file
        "associated_data_b64": base64.b64encode(associated_data).decode()
        if associated_data
        else None,
    }


def decrypt_bytes(ciphertext: bytes, nonce_b64: str, associated_data_b64: str | None = None) -> bytes:
    key = config.aes_key()
    nonce = base64.b64decode(nonce_b64)
    aad = base64.b64decode(associated_data_b64) if associated_data_b64 else None
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, aad)


def encrypt_file(plaintext: bytes, paper_id: str) -> dict:
    """Encrypt and write to the encrypted store. Returns metadata for Mongo."""
    os.makedirs(config.ENCRYPTED_DIR, exist_ok=True)
    aad = paper_id.encode()
    result = encrypt_bytes(plaintext, aad)
    path = os.path.join(config.ENCRYPTED_DIR, f"{paper_id}.enc")
    with open(path, "wb") as fh:
        fh.write(result["ciphertext"])
    return {
        "encrypted_path": path,
        "algorithm": result["algorithm"],
        "nonce_b64": result["nonce_b64"],
        "associated_data_b64": result["associated_data_b64"],
        "size_bytes": len(result["ciphertext"]),
    }


def decrypt_file(meta: dict) -> bytes:
    with open(meta["encrypted_path"], "rb") as fh:
        ciphertext = fh.read()
    return decrypt_bytes(ciphertext, meta["nonce_b64"], meta.get("associated_data_b64"))
