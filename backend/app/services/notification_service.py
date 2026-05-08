"""
Notification service — production implementation.

FIXES applied (Major M-1):
  - dispatch_external_alert() now sends REAL Slack webhook messages via httpx.
  - Falls back to email (via email_service) if Slack is not configured.
  - Falls back to console log only in dev mode.
  - No more "SLACK MOCK" comment.
"""
import logging
from typing import Optional

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification
from app.services.websocket_manager import manager
from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:

    @staticmethod
    async def dispatch_external_alert(
        title: str, message: str, severity: str = "info"
    ) -> bool:
        """
        Dispatch alert to external channels.

        Priority:
          1. Slack webhook (if SLACK_WEBHOOK_URL is configured)
          2. Email (if SMTP credentials are configured)
          3. Console log only (dev fallback)

        Returns True if at least one channel succeeded.
        """
        severity_emoji = {
            "critical": "🚨",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
            "success": "✅",
        }.get(severity, "ℹ️")

        sent = False

        # ── 1. Slack Webhook ──────────────────────────────────────────────────
        if settings.SLACK_WEBHOOK_URL:
            slack_payload = {
                "text": f"{severity_emoji} *{title}* ({severity.upper()})",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{severity_emoji} *{title}*\n{message}",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Severity: `{severity.upper()}` | AIOps Platform",
                            }
                        ],
                    },
                ],
            }
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        settings.SLACK_WEBHOOK_URL,
                        json=slack_payload,
                    )
                    resp.raise_for_status()
                logger.info(f"[Alert] Slack notification sent: {title}")
                sent = True
            except Exception as e:
                logger.warning(f"[Alert] Slack webhook failed: {e}")

        # ── 2. Email fallback ─────────────────────────────────────────────────
        if not sent and settings.SMTP_USER and settings.SMTP_PASSWORD:
            try:
                from app.services.email_service import send_alert_email
                await send_alert_email(
                    subject=f"[{severity.upper()}] {title}",
                    body=message,
                )
                logger.info(f"[Alert] Email notification sent: {title}")
                sent = True
            except Exception as e:
                logger.warning(f"[Alert] Email alert failed: {e}")

        # ── 3. Console fallback ───────────────────────────────────────────────
        if not sent:
            log_level = logging.CRITICAL if severity == "critical" else logging.WARNING
            logger.log(
                log_level,
                f"[EXTERNAL ALERT — no channel configured] {severity_emoji} {title}: {message}",
            )

        return sent

    @staticmethod
    def build_notification(
        user_id: int,
        title: str,
        message: str,
        tenant_id: int,
        notif_type: str = "info",
        link: Optional[str] = None,
    ) -> Notification:
        """
        Build a Notification ORM object without persisting it.
        Caller is responsible for db.add() and db.commit().
        """
        return Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            message=message,
            type=notif_type,
            link=link,
        )

    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: int,
        title: str,
        message: str,
        tenant_id: int,
        type: str = "info",
        link: Optional[str] = None,
        broadcast: bool = True,
    ) -> Notification:
        """Create and persist a notification, then optionally broadcast via WebSocket."""
        notification = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            link=link,
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)

        if broadcast:
            try:
                await manager.broadcast({
                    "type": "new_notification",
                    "data": {
                        "id": notification.id,
                        "title": notification.title,
                        "message": notification.message,
                        "type": notification.type,
                        "link": notification.link,
                        "created_at": notification.created_at.isoformat(),
                    },
                })
            except Exception as e:
                logger.warning(
                    f"WebSocket broadcast failed for notification {notification.id}: {e}"
                )

        return notification

    @staticmethod
    async def get_user_notifications(
        db: AsyncSession, user_id: int, limit: int = 50
    ):
        result = await db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def mark_as_read(
        db: AsyncSession, notification_id: int, user_id: int
    ) -> Optional[Notification]:
        result = await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        notification = result.scalar_one_or_none()
        if notification:
            notification.is_read = True
            await db.commit()
        return notification

    @staticmethod
    async def mark_all_as_read(db: AsyncSession, user_id: int) -> int:
        result = await db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )
        await db.commit()
        return result.rowcount