"""
PII Field Encryption Service — AES-256-GCM encryption for sensitive fields.

Encrypts/decrypts PII fields (first_name, last_name, date_of_birth) using
AES-256-GCM. When encryption_key is empty (dev mode), stores plaintext
with a logged warning.
"""

import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

logger = logging.getLogger(__name__)

# Prefix to identify encrypted values
_ENCRYPTED_PREFIX = "enc::"


def _get_key() -> bytes | None:
    """Derive a 32-byte key from settings. Returns None if not configured."""
    raw = settings.encryption_key
    if not raw:
        return None
    # Accept base64-encoded 32-byte key or raw string hashed to 32 bytes
    try:
        decoded = base64.b64decode(raw)
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    # Fallback: use SHA-256 of the key string
    import hashlib
    return hashlib.sha256(raw.encode()).digest()


def encrypt_field(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns ciphertext as base64 string."""
    if not plaintext:
        return plaintext

    key = _get_key()
    if key is None:
        logger.warning("PII encryption key not configured — storing plaintext")
        return plaintext

    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Format: enc::<base64(nonce + ciphertext)>
    payload = base64.b64encode(nonce + ciphertext).decode("ascii")
    return f"{_ENCRYPTED_PREFIX}{payload}"


def decrypt_field(value: str) -> str:
    """Decrypt an encrypted field. Returns plaintext. Passes through unencrypted values."""
    if not value or not value.startswith(_ENCRYPTED_PREFIX):
        return value

    key = _get_key()
    if key is None:
        logger.warning("Cannot decrypt — encryption key not configured")
        return value

    payload = base64.b64decode(value[len(_ENCRYPTED_PREFIX):])
    nonce = payload[:12]
    ciphertext = payload[12:]

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def is_encrypted(value: str) -> bool:
    """Check if a value is encrypted."""
    return bool(value) and value.startswith(_ENCRYPTED_PREFIX)
