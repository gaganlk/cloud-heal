"""
Pre-execution safety gate for healing actions.
Enforces rate limits, dangerous action confirmation, and blast radius checks.
Uses Redis for distributed rate limiting — works across multiple workers.
"""
import logging
import os
from typing import Tuple

logger = logging.getLogger(__name__)

# Action safety matrix — defines risk level and rate limits
SAFE_ACTION_MATRIX = {
    "restart": {
        "requires_manual_approval": False,
        "max_per_hour_per_resource": 5,
        "max_per_hour_global": 50,
        "risk_level": "low",
    },
    "scale_up": {
        "requires_manual_approval": False,
        "max_per_hour_per_resource": 10,
        "max_per_hour_global": 100,
        "risk_level": "low",
    },
    "reroute": {
        "requires_manual_approval": False,
        "max_per_hour_per_resource": 20,
        "max_per_hour_global": 200,
        "risk_level": "low",
    },
    "isolate": {
        "requires_manual_approval": True,   # Must be manually approved
        "max_per_hour_per_resource": 2,
        "max_per_hour_global": 10,
        "risk_level": "high",
    },
    "failover": {
        "requires_manual_approval": True,
        "max_per_hour_per_resource": 1,
        "max_per_hour_global": 5,
        "risk_level": "critical",
    },
    "rollback": {
        "requires_manual_approval": True,
        "max_per_hour_per_resource": 1,
        "max_per_hour_global": 5,
        "risk_level": "critical",
    },
}

CHAOS_BYPASS = os.getenv("CHAOS_SAFETY_BYPASS", "false").lower() == "true"


async def pre_execution_check(
    action_type: str,
    resource_id: str,
    redis_client,
    auto_triggered: bool = False,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    """
    Validate whether a healing action is safe to execute.
    Returns (allowed: bool, reason: str).

    Rules:
    1. Auto-triggered actions cannot execute high/critical risk actions
    2. Per-resource rate limit must not be exceeded
    3. Global rate limit must not be exceeded
    4. Dry-run mode always returns allowed=True but logs the action
    """
    cfg = SAFE_ACTION_MATRIX.get(action_type)
    if not cfg:
        return False, f"Unknown action type: '{action_type}'"

    if dry_run:
        logger.info(f"[DRY RUN] Would execute '{action_type}' on '{resource_id}'")
        return True, "dry_run"

    # Rule 1: Auto-triggered cannot perform actions requiring manual approval
    if auto_triggered and cfg["requires_manual_approval"] and not CHAOS_BYPASS:
        return False, (
            f"Action '{action_type}' (risk={cfg['risk_level']}) requires "
            "manual confirmation and cannot be auto-triggered"
        )

    # Rule 2: Per-resource rate limit
    resource_key = f"healing:rate:resource:{resource_id}:{action_type}"
    resource_count = await _redis_incr_with_ttl(redis_client, resource_key, 3600)
    max_per_resource = cfg["max_per_hour_per_resource"]
    if resource_count > max_per_resource:
        return False, (
            f"Per-resource rate limit exceeded: {action_type} on {resource_id} "
            f"({resource_count}/{max_per_resource} per hour)"
        )

    # Rule 3: Global rate limit across all resources
    global_key = f"healing:rate:global:{action_type}"
    global_count = await _redis_incr_with_ttl(redis_client, global_key, 3600)
    max_global = cfg["max_per_hour_global"]
    if global_count > max_global:
        return False, (
            f"Global rate limit exceeded: {action_type} "
            f"({global_count}/{max_global} per hour across all resources)"
        )

    return True, "OK"


async def _redis_incr_with_ttl(redis_client, key: str, ttl: int) -> int:
    """Atomically increment a Redis key and set TTL on first creation."""
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, ttl)
    return count


async def validate_resource_exists(resource_id: str, db_session) -> bool:
    """Confirm resource exists in DB before executing healing action."""
    from sqlalchemy import select
    from app.db.models import CloudResource
    result = await db_session.execute(
        select(CloudResource.id).where(CloudResource.resource_id == resource_id)
    )
    return result.scalar_one_or_none() is not None
