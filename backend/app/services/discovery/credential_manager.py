"""
Real credential manager that decrypts credentials from the encrypted DB column.
Provides a HashiCorp Vault-compatible interface that can be swapped in Phase 9.
"""
import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ── Fernet encryption (same key used in backend/services/encryption.py) ──────
def _get_fernet():
    from cryptography.fernet import Fernet
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY environment variable is not set")
    return Fernet(key.encode() if isinstance(key, str) else key)


class CredentialManager:
    """
    Enterprise credential manager.
    - Phase 1-8: decrypts from Fernet-encrypted DB column
    - Phase 9+: drop-in Vault integration by overriding get_aws_credentials()
    """

    @staticmethod
    def decrypt_credentials(encrypted_data: str) -> dict:
        """Decrypt a Fernet-encrypted credential blob and return as dict."""
        f = _get_fernet()
        plain = f.decrypt(encrypted_data.encode()).decode()
        return json.loads(plain)

    @staticmethod
    def encrypt_credentials(credentials: dict) -> str:
        """Encrypt a credentials dict for storage in DB."""
        f = _get_fernet()
        plain = json.dumps(credentials).encode()
        return f.encrypt(plain).decode()

    @staticmethod
    async def get_credentials_for_id(db_session, credential_id: int) -> dict:
        """
        Look up a CloudCredential by PK and return decrypted values.
        Raises ValueError if not found.
        """
        from sqlalchemy import select
        from app.db.models import CloudCredential

        result = await db_session.execute(
            select(CloudCredential).where(CloudCredential.id == credential_id)
        )
        cred = result.scalar_one_or_none()
        if not cred:
            raise ValueError(f"Credential {credential_id} not found in database")
        return CredentialManager.decrypt_credentials(cred.encrypted_data)

    @staticmethod
    def get_aws_credentials(tenant_id: str, provider_id: str) -> Dict:
        """
        Vault-compatible interface.
        In production: replace body with Vault KV lookup:
            vault_client.secrets.kv.v2.read_secret_version(
                path=f"{tenant_id}/aws/{provider_id}"
            )
        Currently: raises NotImplementedError to prevent silent placeholder usage.
        """
        vault_addr = os.getenv("VAULT_ADDR")
        vault_token = os.getenv("VAULT_TOKEN")

        if vault_addr and vault_token:
            return CredentialManager._fetch_from_vault(tenant_id, provider_id, vault_addr, vault_token)

        raise NotImplementedError(
            "Vault not configured. Use get_credentials_for_id() with a DB session "
            "or configure VAULT_ADDR + VAULT_TOKEN environment variables."
        )

    @staticmethod
    def _fetch_from_vault(tenant_id: str, provider_id: str, vault_addr: str, vault_token: str) -> dict:
        """Fetch secrets from HashiCorp Vault KV v2."""
        try:
            import hvac
            client = hvac.Client(url=vault_addr, token=vault_token)
            if not client.is_authenticated():
                raise RuntimeError("Vault token is invalid or expired")
            secret = client.secrets.kv.v2.read_secret_version(
                path=f"{tenant_id}/aws/{provider_id}",
                mount_point="secret",
            )
            return secret["data"]["data"]
        except ImportError:
            raise RuntimeError("hvac package not installed. Run: pip install hvac")
        except Exception as e:
            raise RuntimeError(f"Vault fetch failed: {e}")
