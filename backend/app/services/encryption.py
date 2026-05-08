"""
Credential encryption/decryption using Fernet symmetric encryption.

FIXES applied (Critical C-3):
  - Removed module-level Fernet initialization (_key / _fernet at import time).
    The old code would silently generate a throwaway key in Docker (read-only
    filesystem) and encrypt credentials that could never be decrypted after restart.
  - Now uses a lazy getter: _get_fernet() is called at the point of use.
  - Raises RuntimeError with a clear message if ENCRYPTION_KEY is missing.
  - No file-write side-effects on import.
"""
import json
import os
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    """
    Return a Fernet instance from the ENCRYPTION_KEY environment variable.
    Raises RuntimeError with a helpful message if the key is missing or invalid.
    """
    key_str = os.getenv("ENCRYPTION_KEY", "")
    if not key_str:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
            "and add it to your .env file."
        )
    try:
        key_bytes = key_str.encode() if isinstance(key_str, str) else key_str
        return Fernet(key_bytes)
    except Exception as e:
        raise RuntimeError(
            f"ENCRYPTION_KEY is invalid: {e}. "
            "It must be a valid 32-byte URL-safe base64-encoded Fernet key."
        ) from e


def validate_encryption_key() -> None:
    """
    Call this at application startup to fail fast if the key is missing/invalid.
    Raises RuntimeError with a clear message.
    """
    _get_fernet()   # Will raise if invalid


def encrypt_credentials(data: dict) -> str:
    """Encrypt a credentials dictionary to a safe string."""
    f = _get_fernet()
    json_data = json.dumps(data)
    return f.encrypt(json_data.encode()).decode()


def decrypt_credentials(encrypted_data: str) -> dict:
    """
    Decrypt a credentials string back to a dictionary.
    Raises cryptography.fernet.InvalidToken if the data was encrypted with a
    different key (e.g., after an ENCRYPTION_KEY rotation without migration).
    """
    f = _get_fernet()
    try:
        decrypted = f.decrypt(encrypted_data.encode())
        return json.loads(decrypted.decode())
    except InvalidToken:
        raise RuntimeError(
            "Credential decryption failed: the stored credentials were encrypted "
            "with a different ENCRYPTION_KEY. Re-enter the credentials or restore "
            "the original key."
        )