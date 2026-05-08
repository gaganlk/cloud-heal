import os
from cryptography.fernet import Fernet
from app.core.config import settings

def validate_encryption_key():
    """
    Validates that the ENCRYPTION_KEY environment variable is a valid Fernet key.
    """
    key = settings.ENCRYPTION_KEY
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is not set in environment.")
    
    try:
        # Fernet keys must be 32 url-safe base64-encoded bytes
        Fernet(key)
    except Exception as e:
        raise RuntimeError(f"Invalid ENCRYPTION_KEY provided: {e}")

def encrypt_data(data: str) -> str:
    """Encrypts a string using the ENCRYPTION_KEY."""
    f = Fernet(settings.ENCRYPTION_KEY)
    return f.encrypt(data.encode()).decode()

def decrypt_data(token: str) -> str:
    """Decrypts a token using the ENCRYPTION_KEY."""
    f = Fernet(settings.ENCRYPTION_KEY)
    return f.decrypt(token.encode()).decode()
