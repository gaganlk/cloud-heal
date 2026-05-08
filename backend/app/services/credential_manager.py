"""
Production CredentialManager with three-tier priority:
  1. HashiCorp Vault (if VAULT_ADDR + VAULT_TOKEN configured)
  2. AWS Secrets Manager (if AWS_DEFAULT_REGION configured)
  3. Fernet-encrypted DB column (existing fallback)
"""
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _get_fernet():
    from cryptography.fernet import Fernet
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY environment variable is not set")
    return Fernet(key.encode() if isinstance(key, str) else key)


class CredentialManager:
    """
    Enterprise three-tier credential manager.
    Priority: Vault → AWS Secrets Manager → DB (Fernet-encrypted)
    """

    # ── DB Encryption Layer ───────────────────────────────────────────────────
    @staticmethod
    def decrypt_credentials(encrypted_data: str) -> dict:
        f = _get_fernet()
        plain = f.decrypt(encrypted_data.encode()).decode()
        return json.loads(plain)

    @staticmethod
    def encrypt_credentials(credentials: dict) -> str:
        f = _get_fernet()
        return f.encrypt(json.dumps(credentials).encode()).decode()

    # ── Primary DB Lookup ─────────────────────────────────────────────────────
    @staticmethod
    async def get_credentials_for_id(db_session, credential_id: int) -> dict:
        """
        Look up CloudCredential by PK, returning decrypted values.
        Tries Vault first if configured, then DB fallback.
        """
        from sqlalchemy import select
        from app.db.models import CloudCredential

        result = await db_session.execute(
            select(CloudCredential).where(CloudCredential.id == credential_id)
        )
        cred = result.scalar_one_or_none()
        if not cred:
            raise ValueError(f"Credential {credential_id} not found")

        # Try Vault first
        vault_path = f"cloud-healing/{cred.provider}/{credential_id}"
        vault_data = CredentialManager._try_vault(vault_path)
        if vault_data:
            logger.info(f"Credential {credential_id} retrieved from Vault")
            return vault_data

        # Try AWS Secrets Manager
        secret_name = f"cloud-healing/{cred.provider}/cred-{credential_id}"
        aws_data = CredentialManager._try_aws_secrets_manager(secret_name)
        if aws_data:
            logger.info(f"Credential {credential_id} retrieved from AWS Secrets Manager")
            return aws_data

        # DB fallback
        logger.debug(f"Credential {credential_id} retrieved from encrypted DB")
        return CredentialManager.decrypt_credentials(cred.encrypted_data)

    # ── Vault Integration ─────────────────────────────────────────────────────
    @staticmethod
    def _try_vault(path: str) -> Optional[Dict[str, Any]]:
        """Fetch from HashiCorp Vault KV v2. Returns None if unavailable."""
        vault_addr = os.getenv("VAULT_ADDR")
        vault_token = os.getenv("VAULT_TOKEN")
        vault_mount = os.getenv("VAULT_MOUNT", "secret")

        if not (vault_addr and vault_token):
            return None

        try:
            import hvac
            client = hvac.Client(url=vault_addr, token=vault_token)
            if not client.is_authenticated():
                logger.warning("Vault token is invalid/expired")
                return None
            secret = client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=vault_mount,
            )
            return secret["data"]["data"]
        except Exception as e:
            logger.debug(f"Vault lookup failed for '{path}': {e}")
            return None

    @staticmethod
    def store_in_vault(credential_id: int, provider: str, data: dict) -> bool:
        """Store credentials in Vault. Returns True on success."""
        vault_addr = os.getenv("VAULT_ADDR")
        vault_token = os.getenv("VAULT_TOKEN")
        vault_mount = os.getenv("VAULT_MOUNT", "secret")

        if not (vault_addr and vault_token):
            return False

        try:
            import hvac
            client = hvac.Client(url=vault_addr, token=vault_token)
            path = f"cloud-healing/{provider}/cred-{credential_id}"
            client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data,
                mount_point=vault_mount,
            )
            logger.info(f"Credential {credential_id} stored in Vault at {path}")
            return True
        except Exception as e:
            logger.warning(f"Vault store failed: {e}")
            return False

    # ── AWS Secrets Manager ───────────────────────────────────────────────────
    @staticmethod
    def _try_aws_secrets_manager(secret_name: str) -> Optional[Dict[str, Any]]:
        """Fetch from AWS Secrets Manager. Returns None if unavailable."""
        region = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION")
        if not region:
            return None

        try:
            import boto3
            client = boto3.client("secretsmanager", region_name=region)
            resp = client.get_secret_value(SecretId=secret_name)
            raw = resp.get("SecretString")
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.debug(f"AWS Secrets Manager lookup failed: {e}")
        return None

    @staticmethod
    def store_in_aws_secrets_manager(secret_name: str, data: dict) -> bool:
        """Store credentials in AWS Secrets Manager."""
        region = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION")
        if not region:
            return False

        try:
            import boto3
            client = boto3.client("secretsmanager", region_name=region)
            try:
                client.create_secret(Name=secret_name, SecretString=json.dumps(data))
            except client.exceptions.ResourceExistsException:
                client.update_secret(SecretId=secret_name, SecretString=json.dumps(data))
            logger.info(f"Credential stored in AWS Secrets Manager: {secret_name}")
            return True
        except Exception as e:
            logger.warning(f"AWS Secrets Manager store failed: {e}")
            return False

    # ── Vault status check ────────────────────────────────────────────────────
    @staticmethod
    def vault_status() -> dict:
        """Return Vault connectivity status for health dashboard."""
        vault_addr = os.getenv("VAULT_ADDR")
        vault_token = os.getenv("VAULT_TOKEN")

        if not vault_addr:
            return {"status": "not_configured", "addr": None}

        try:
            import hvac
            client = hvac.Client(url=vault_addr, token=vault_token)
            auth = client.is_authenticated()
            return {"status": "connected" if auth else "unauthenticated", "addr": vault_addr}
        except Exception as e:
            return {"status": "error", "addr": vault_addr, "error": str(e)}
