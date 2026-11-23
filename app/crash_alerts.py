"""Email the admin when the website crashes, so a broken screen is noticed in minutes, not at the next
look at the Inbox.

At most one email per kind of crash (same message on the same screen) per hour, so a broken screen
that many people hit doesn't flood the inbox; the next email says how many more happened meanwhile.

Who gets it (Railway → service → Variables):
  CRASH_EMAIL_TO  optional, comma-separated addresses; otherwise ADMIN_EMAIL.
Needs the same mail settings as password resets (RESEND_API_KEY, MAIL_FROM, PUBLIC_URL). Without
them, or without a recipient, nothing is sent and crashes still reach the Inbox.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any, Optional

from app import mailer
from app.db.database import now

log = logging.getLogger("dinnerdesk.crash_alerts")

EVERY = timedelta(hours=1)


def recipients() -> list[str]:
    raw = os.environ.get("CRASH_EMAIL_TO") or os.environ.get("ADMIN_EMAIL") or ""
    return [a.strip() for a in raw.split(",") if a.strip()]


def due(conn: Any, message: str, screen: str) -> Optional[int]:
    """Count this crash. Returns how many happened since the last email when one is due now, else None.
    Call inside the report's transaction."""
    key = f"{screen}\n{message}"[:800]
    row = conn.execute("SELECT last_sent_at, pending FROM crash_alerts WHERE key = ?", (key,)).fetchone()
    stamp = now()
    if row is None:
        conn.execute("INSERT INTO crash_alerts (key, last_sent_at, pending) VALUES (?, ?, 0) ON CONFLICT DO NOTHING",
                     (key, stamp))
        return 1
    last = datetime.fromisoformat(row["last_sent_at"])
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - last < EVERY:
        conn.execute("UPDATE crash_alerts SET pending = pending + 1 WHERE key = ?", (key,))
        return None
    conn.execute("UPDATE crash_alerts SET last_sent_at = ?, pending = 0 WHERE key = ?", (stamp, key))
    return row["pending"] + 1


def send(message: str, screen: str, count: int, device: str) -> None:
    """Send the email. Runs after the response; never raises, since a failed email must not matter."""
    to = recipients()
    if not to or not mailer.mail_ready():
        return
    try:
        inbox = f"{mailer.public_url()}/admin/inbox"
        times = "once" if count == 1 else f"{count} times in the last hour"
        subject = f"Dinner Desk crash on {screen or 'a screen'}"
        text = (f"The website crashed {times}.\n\nScreen: {screen or '(unknown)'}\nError: {message}\n"
                f"Device: {device or '(unknown)'}\n\nThe stack and the pages before it are in the Inbox:\n{inbox}\n\n"
                "You'll get at most one email an hour for this crash.")
        html = (f"<p>The website crashed {escape(times)}.</p>"
                f"<p><b>Screen:</b> {escape(screen or '(unknown)')}<br><b>Error:</b> {escape(message)}<br>"
                f"<b>Device:</b> {escape(device or '(unknown)')}</p>"
                f'<p><a href="{escape(inbox)}">Open the Inbox</a> for the stack and the pages before it.</p>'
                "<p>You'll get at most one email an hour for this crash.</p>")
        for address in to:
            mailer._send(address, subject, text, html)
    except Exception:  # noqa: BLE001 - email trouble must not break crash reporting
        log.exception("crash email failed")
