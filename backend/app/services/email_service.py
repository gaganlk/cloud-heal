"""
Email service — async SMTP with HTML templates.

Added:
  - send_alert_email() for external alerting (NotificationService fallback)
"""
import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_smtp_config() -> dict:
    return {
        "server": settings.SMTP_SERVER,
        "port": settings.SMTP_PORT,
        "user": settings.SMTP_USER,
        "password": settings.SMTP_PASSWORD,
        "sender": settings.SENDER_EMAIL or settings.SMTP_USER,
    }


def _smtp_configured() -> bool:
    cfg = _get_smtp_config()
    return bool(cfg["user"] and cfg["password"])


async def send_otp_email(email: str, otp: str) -> None:
    """
    Sends a high-premium HTML OTP email to the user.
    If SMTP is not configured, logs the OTP to console (dev mode only).
    """
    if not _smtp_configured():
        logger.warning(
            "SMTP credentials not configured (SMTP_USER / SMTP_PASSWORD missing). "
            f"DEV OTP for {email}: {otp}"
        )
        return

    cfg = _get_smtp_config()
    message = MIMEMultipart("alternative")
    message["Subject"] = f"Verification Code: {otp} | {settings.APP_NAME}"
    message["From"] = f"{settings.APP_NAME} <{cfg['sender']}>"
    message["To"] = email

    html = f"""
    <html>
      <body style="font-family: 'Inter', sans-serif; background-color: #f8fafc; padding: 40px;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 24px;
                    overflow: hidden; box-shadow: 0 20px 50px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;">
          <div style="background: linear-gradient(135deg, #0ea5e9, #6366f1); padding: 40px; text-align: center;">
            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 900;">
              Verify Your Identity
            </h1>
          </div>
          <div style="padding: 40px; text-align: center;">
            <p style="color: #64748b; font-size: 16px; margin-bottom: 32px;">
              Use this code to complete your login or registration.
            </p>
            <div style="background: #f1f5f9; border-radius: 16px; padding: 24px; display: inline-block;">
              <span style="font-family: monospace; font-size: 40px; font-weight: 900;
                           letter-spacing: 12px; color: #0f172a;">{otp}</span>
            </div>
            <p style="color: #94a3b8; font-size: 12px; margin-top: 32px; text-transform: uppercase;">
              Expires in 10 minutes
            </p>
          </div>
          <div style="padding: 24px; background: #f8fafc; border-top: 1px solid #f1f5f9; text-align: center;">
            <p style="color: #94a3b8; font-size: 12px; margin: 0;">
              If you didn't request this code, you can safely ignore this email.
            </p>
          </div>
        </div>
      </body>
    </html>
    """
    message.attach(MIMEText(html, "html"))

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_smtp, cfg, message, email)
    logger.info(f"OTP email sent to {email}")


async def send_alert_email(subject: str, body: str) -> None:
    """
    Send a plain-text alert email to SENDER_EMAIL (admin mailbox).
    Used as Slack webhook fallback in NotificationService.
    """
    if not _smtp_configured():
        logger.warning(f"SMTP not configured. Alert not emailed: {subject}")
        return

    cfg = _get_smtp_config()
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.APP_NAME} <{cfg['sender']}>"
    message["To"] = cfg["sender"]   # Alert goes to the admin's own mailbox

    html = f"""
    <html><body style="font-family:sans-serif;padding:20px;">
    <h2 style="color:#0f172a;">{subject}</h2>
    <p style="color:#334155;">{body}</p>
    <p style="color:#94a3b8;font-size:12px;">Sent by {settings.APP_NAME}</p>
    </body></html>
    """
    message.attach(MIMEText(html, "html"))

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_smtp, cfg, message, cfg["sender"])
    logger.info(f"Alert email sent: {subject}")


def _send_smtp(cfg: dict, message: MIMEMultipart, recipient: str) -> None:
    """Synchronous SMTP send — runs in executor to avoid blocking the event loop."""
    with smtplib.SMTP(cfg["server"], cfg["port"], timeout=10) as server:
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.sendmail(cfg["sender"], recipient, message.as_string())