import re
from typing import Tuple, List

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validates that a password is strong.
    Rules:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (@$!%*?&)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    
    if not re.search(r"[@$!%*?&]", password):
        return False, "Password must contain at least one special character (@$!%*?&)."
    
    return True, "Strong password."

def validate_aws_credentials(access_key: str, secret_key: str) -> bool:
    """Basic pattern check for AWS credentials."""
    # AKIA... (20 chars) or ASIA... (20 chars)
    aws_access_key_pattern = r"^(AKIA|ASIA)[0-9A-Z]{16}$"
    # 40 chars base64-like
    aws_secret_key_pattern = r"^[A-Za-z0-9/+=]{40}$"
    
    return bool(re.match(aws_access_key_pattern, access_key) and re.match(aws_secret_key_pattern, secret_key))

def validate_guid(guid: str) -> bool:
    """Enforces GUID/UUID format xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"""
    pattern = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    return bool(re.match(pattern, guid))
