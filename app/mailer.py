"""Outgoing email (password reset and email confirmation links) through Resend's HTTP API.

Set on the server (Railway → service → Variables):
  RESEND_API_KEY  key from resend.com → API Keys
  MAIL_FROM       required, e.g. "Dinnerdesk <hello@yourdomain.com>" once a domain is verified.
  PUBLIC_URL      required, the app website origin

Missing credentials and delivery failures raise immediately.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request

log = logging.getLogger("dinnerdesk.mail")



def mail_ready() -> bool:
    """True when the server has what it needs to send email (key, sender, site address)."""
    return all((os.environ.get(k) or "").strip() for k in ("RESEND_API_KEY", "MAIL_FROM", "PUBLIC_URL"))


def public_url() -> str:
    url = (os.environ.get("PUBLIC_URL") or "").strip()
    if not url:
        raise RuntimeError("PUBLIC_URL is required for emailed links")
    return url.rstrip("/")


def reset_link(token: str) -> str:
    return f"{public_url()}/reset/{token}"


def verify_link(token: str) -> str:
    return f"{public_url()}/verify/{token}"


def send_reset_email(to: str, link: str) -> bool:
    """Send the reset email. Raises on missing credentials or failed delivery."""
    return _send(
        to,
        "Reset your Dinnerdesk password",
        (
            "Someone (hopefully you) asked to reset your Dinnerdesk password.\n\n"
            f"Set a new password here (the link works once, for 1 hour):\n{link}\n\n"
            "If you didn't ask for this, you can ignore this email; your password hasn't changed."
        ),
        (
            "<p>Someone (hopefully you) asked to reset your Dinnerdesk password.</p>"
            f'<p><a href="{link}">Set a new password</a></p>'
            "<p>The link works once, for 1 hour. If you didn't ask for this, you can ignore this "
            "email; your password hasn't changed.</p>"
        ),
    )


def send_verify_email(to: str, link: str) -> bool:
    """Send the confirm-this-address email. Raises on missing credentials or failed delivery."""
    return _send(
        to,
        "Confirm your Dinnerdesk email",
        (
            "Someone (hopefully you) added this address to a Dinnerdesk account.\n\n"
            f"Confirm it here (the link works once, for 24 hours):\n{link}\n\n"
            "If this wasn't you, you can ignore this email; nothing changes until the link is opened."
        ),
        (
            "<p>Someone (hopefully you) added this address to a Dinnerdesk account.</p>"
            f'<p><a href="{link}">Confirm this email</a></p>'
            "<p>The link works once, for 24 hours. If this wasn't you, you can ignore this email; "
            "nothing changes until the link is opened.</p>"
        ),
    )


def _send(to: str, subject: str, text: str, html: str) -> bool:
    key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("RESEND_API_KEY is required to send email")
    sender = (os.environ.get("MAIL_FROM") or "").strip()
    if not sender:
        raise RuntimeError("MAIL_FROM is required to send email")
    body = {"from": sender, "to": [to], "subject": subject, "text": text, "html": html}
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode("utf-8"),
        # Resend's Cloudflare front blocks urllib's default User-Agent with a 403 (error 1010).
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "dinnerdesk/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Email delivery failed ({response.status})")
        return True
