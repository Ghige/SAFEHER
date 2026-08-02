"""
Encryption service for sensitive fields stored in the DB.

Currently used for: User.drive_token (Google Drive OAuth token).

Generates a Fernet symmetric key. Store the key in DRIVE_TOKEN_ENCRYPTION_KEY
in your .env file. Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

If DRIVE_TOKEN_ENCRYPTION_KEY is not set, encryption is skipped with a warning.
DO NOT deploy to production without setting this key.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_fernet = None
_warned = False


def _get_fernet():
    global _fernet, _warned
    if _fernet is not None:
        return _fernet

    from app.config import settings
    key = settings.DRIVE_TOKEN_ENCRYPTION_KEY

    if not key:
        if not _warned:
            logger.warning(
                "DRIVE_TOKEN_ENCRYPTION_KEY is not set. "
                "Drive tokens will be stored unencrypted. "
                "Set this key before deploying to production."
            )
            _warned = True
        return None

    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return _fernet
    except Exception as e:
        logger.error(f"Failed to initialise Fernet encryption: {e}")
        return None


def encrypt_token(plaintext: str) -> str:
    """
    Encrypt a token string for DB storage.
    Returns the ciphertext as a string, or the original if no key is configured.
    """
    if not plaintext:
        return plaintext
    f = _get_fernet()
    if f is None:
        return plaintext
    try:
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error(f"Token encryption failed: {e}")
        return plaintext


def decrypt_token(ciphertext: str) -> Optional[str]:
    """
    Decrypt a token retrieved from the DB.
    Returns the plaintext, or None if decryption fails.
    """
    if not ciphertext:
        return ciphertext
    f = _get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        logger.error(f"Token decryption failed: {e}")
        return None
