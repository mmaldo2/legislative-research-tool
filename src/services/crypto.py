"""Application-level encryption for secrets stored at rest.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the cryptography library.
When WEBHOOK_ENCRYPTION_KEY is not set, secrets are stored as plaintext
(acceptable for development; must be configured in production).
"""

import logging

from cryptography.fernet import Fernet, InvalidToken

from src.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet | None:
    """Return a cached Fernet instance, or None if no key is configured."""
    global _fernet
    if _fernet is not None:
        return _fernet
    if not settings.webhook_encryption_key:
        return None
    _fernet = Fernet(settings.webhook_encryption_key.encode())
    return _fernet


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret for storage. Returns ciphertext or plaintext if no key configured."""
    f = _get_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_secret(stored: str) -> str:
    """Decrypt a stored secret. Falls back to returning as-is if not encrypted."""
    f = _get_fernet()
    if f is None:
        return stored
    try:
        return f.decrypt(stored.encode()).decode()
    except InvalidToken:
        # Not encrypted (legacy plaintext value) — return as-is
        return stored
