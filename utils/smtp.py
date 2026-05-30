"""Outbound email via SMTP (Gmail / Google Workspace with app passwords)."""

from __future__ import annotations

import os
import smtplib
import ssl
from collections.abc import Iterable
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

SMTP_HOST = os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", "587"))


def _normalize_addrs(addrs: str | Iterable[str]) -> list[str]:
    if isinstance(addrs, str):
        return [addrs]
    return list(addrs)


def smtp_credentials() -> tuple[str, str]:
    user = os.environ.get("EMAIL_USER")
    raw_password = os.environ.get("EMAIL_PASSWORD")
    if not user or not raw_password:
        raise RuntimeError("Set EMAIL_USER and EMAIL_PASSWORD in .env")
    # Google app passwords are often copied with spaces between groups
    password = raw_password.replace(" ", "").strip()
    return user, password


def send_email(
    *,
    to_addrs: str | Iterable[str],
    subject: str,
    body: str,
    html_body: str | None = None,
    cc: str | Iterable[str] | None = None,
    reply_to: str | None = None,
    timeout: float = 30.0,
) -> None:
    """
    Send a message from EMAIL_USER. Uses STARTTLS on SMTP_PORT (default 587).
    """
    user, password = smtp_credentials()
    recipients = _normalize_addrs(to_addrs)
    cc_list = _normalize_addrs(cc) if cc else []

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.set_content(body)
    if html_body is not None:
        msg.add_alternative(html_body, subtype="html")

    all_recipients = recipients + cc_list
    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=timeout) as server:
        server.starttls(context=ctx)
        server.login(user, password)
        server.send_message(msg, from_addr=user, to_addrs=all_recipients)
