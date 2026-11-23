"""Privacy agreements: who agreed to which version of the privacy summary, and when.

A guest agrees once per guest kitchen (the random guest cookie's household, no IP address). An
account agrees at signup and again whenever PRIVACY_VERSION changes. Bump PRIVACY_VERSION only
when what we keep or share changes in a way people should see again; every client then shows the
agreement screen once more.
"""

from __future__ import annotations

from typing import Any, Optional

from app.db.database import now

# The date the privacy summary last changed in a way that needs agreeing to again.
PRIVACY_VERSION = "2026-11-21"


def record(conn: Any, household_id: int, user_id: Optional[int]) -> None:
    """Note that this account (or, with no user, this guest kitchen) agreed to the current version."""
    conn.execute(
        "INSERT INTO privacy_agreements (household_id, user_id, kind, policy_version, agreed_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (household_id, user_id, "account" if user_id is not None else "guest", PRIVACY_VERSION, now()),
    )


def agreed(conn: Any, household_id: int, user_id: Optional[int]) -> bool:
    """Has this account (or guest kitchen) agreed to the current version?"""
    if user_id is not None:
        row = conn.execute(
            "SELECT 1 FROM privacy_agreements WHERE user_id = ? AND policy_version = ?",
            (user_id, PRIVACY_VERSION),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM privacy_agreements WHERE household_id = ? AND user_id IS NULL "
            "AND policy_version = ?",
            (household_id, PRIVACY_VERSION),
        ).fetchone()
    return row is not None
