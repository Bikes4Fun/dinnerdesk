"""Outgoing email (password reset links) through Resend's HTTP API.

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



def public_url() -> str:
    url = (os.environ.get("PUBLIC_URL") or "").strip()
    if not url:
        raise RuntimeError("PUBLIC_URL is required for password reset links")
    return url.rstrip("/")


def reset_link(token: str) -> str:
    return f"{public_url()}/reset/{token}"


def send_reset_email(to: str, link: str) -> bool:
    """Send the reset email. Raises on missing credentials or failed delivery."""
    key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("RESEND_API_KEY is required to send password reset emails")
    sender = (os.environ.get("MAIL_FROM") or "").strip()
    if not sender:
        raise RuntimeError("MAIL_FROM is required for password reset emails")
    body = {
        "from": sender,
        "to": [to],
        "subject": "Reset your Dinnerdesk password",
        "text": (
            "Someone (hopefully you) asked to reset your Dinnerdesk password.\n\n"
            f"Set a new password here (the link works once, for 1 hour):\n{link}\n\n"
            "If you didn't ask for this, you can ignore this email; your password hasn't changed."
        ),
        "html": (
            "<p>Someone (hopefully you) asked to reset your Dinnerdesk password.</p>"
            f'<p><a href="{link}">Set a new password</a></p>'
            "<p>The link works once, for 1 hour. If you didn't ask for this, you can ignore this "
            "email; your password hasn't changed.</p>"
        ),
    }
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Password reset email delivery failed ({response.status})")
        return True
