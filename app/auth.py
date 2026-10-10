"""Password hashing + session tokens. Stdlib only (hashlib/secrets)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.db.database import now

PBKDF2_ITERATIONS = 600_000
SESSION_TTL_DAYS = 30
SESSION_COOKIE = "wp_session"

ADMIN_EMAILS = frozenset(
    {
        "garrett.deanna@gmail.com",
        "dtzecha@gmail.com",
    }
)


def is_admin_email(email: str | None) -> bool:
    if not email:
        return False
    return email.strip().lower() in ADMIN_EMAILS

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
INVITE_TTL_DAYS = 7
RESET_TTL_MINUTES = 60
RESET_MAX_PER_HOUR = 3


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, digest = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        check = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        ).hex()
        return hmac.compare_digest(check, digest)
    except (ValueError, AttributeError):
        return False


class AuthError(Exception):
    def __init__(self, detail: str):
        self.detail = detail


def _check_password_strength(password: str) -> None:
    if len(password) < 8:
        raise AuthError("password_too_short")


def signup(conn: Any, email: str, password: str, household_name: str, guest_household_id: int | None = None) -> str:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise AuthError("invalid_email")
    _check_password_strength(password)

    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        raise AuthError("email_taken")

    ts = now()
    users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    home = conn.execute("SELECT id FROM households WHERE id = 1").fetchone()
    name = household_name.strip() or "My household"
    if guest_household_id is not None:
        household_id = guest_household_id
        conn.execute("UPDATE households SET name = ? WHERE id = ?", (name, household_id))
    elif users == 0 and home:
        conn.execute("UPDATE households SET name = ? WHERE id = 1", (name,))
        household_id = 1
    else:
        cur = conn.execute(
            "INSERT INTO households (name, prefs_json, created_at) VALUES (?, '{}', ?)",
            (name, ts),
        )
        household_id = cur.lastrowid

    cur = conn.execute(
        "INSERT INTO users (household_id, email, password_hash, created_at, "
        "failed_attempts, locked_until) VALUES (?, ?, ?, ?, 0, NULL)",
        (household_id, email, hash_password(password), ts),
    )
    user_id = cur.lastrowid
    conn.commit()

    return _create_session(conn, user_id, household_id)


def login(conn: Any, email: str, password: str) -> str:
    email = email.strip().lower()
    row = conn.execute(
        "SELECT id, household_id, password_hash, failed_attempts, locked_until "
        "FROM users WHERE email = ?",
        (email,),
    ).fetchone()

    if not row:
        raise AuthError("invalid_credentials")

    if row["locked_until"]:
        locked_until = datetime.fromisoformat(row["locked_until"])
        if locked_until > datetime.now(timezone.utc):
            raise AuthError("account_locked")

    if not verify_password(password, row["password_hash"]):
        _register_failed_attempt(conn, row["id"], row["failed_attempts"])
        raise AuthError("invalid_credentials")

    if row["failed_attempts"]:
        conn.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
            (row["id"],),
        )
        conn.commit()

    return _create_session(conn, row["id"], row["household_id"])


def _register_failed_attempt(conn: Any, user_id: int, current: int) -> None:
    attempts = current + 1
    locked_until = None
    if attempts >= MAX_FAILED_ATTEMPTS:
        locked_until = (
            datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
        ).replace(microsecond=0).isoformat()
    conn.execute(
        "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
        (attempts, locked_until, user_id),
    )
    conn.commit()


def change_password(conn: Any, user_id: int, current: str, new: str) -> None:
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or not verify_password(current, row["password_hash"]):
        raise AuthError("invalid_credentials")
    _check_password_strength(new)
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new), user_id)
    )
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()


def _reset_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def start_password_reset(conn: Any, email: str) -> Optional[str]:
    """Make a one-time reset token for this email, or None (unknown email, or too many asks).

    Callers must answer the same way either way, so nobody can probe which emails have accounts.
    """
    email = (email or "").strip().lower()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if not row:
        return None
    since = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0).isoformat()
    recent = conn.execute(
        "SELECT COUNT(*) AS c FROM password_resets WHERE user_id = ? AND created_at > ?",
        (row["id"], since),
    ).fetchone()["c"]
    if recent >= RESET_MAX_PER_HOUR:
        return None
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=RESET_TTL_MINUTES)).replace(
        microsecond=0
    ).isoformat()
    conn.execute(
        "INSERT INTO password_resets (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (_reset_hash(token), row["id"], now(), expires),
    )
    conn.commit()
    return token


def finish_password_reset(conn: Any, token: str, new_password: str) -> str:
    """Set a new password from a reset link. Signs out everywhere, then returns a fresh session."""
    row = conn.execute(
        """SELECT pr.user_id, pr.expires_at, pr.used_at, u.household_id
           FROM password_resets pr JOIN users u ON u.id = pr.user_id
           WHERE pr.token_hash = ?""",
        (_reset_hash(token or ""),),
    ).fetchone()
    if not row or row["used_at"]:
        raise AuthError("reset_invalid")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        raise AuthError("reset_expired")
    _check_password_strength(new_password)
    conn.execute(
        "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
        (hash_password(new_password), row["user_id"]),
    )
    # This link and any other open links for the account stop working.
    conn.execute(
        "UPDATE password_resets SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
        (now(), row["user_id"]),
    )
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["user_id"],))
    conn.commit()
    return _create_session(conn, row["user_id"], row["household_id"])


def logout(conn: Any, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()


def logout_everywhere(conn: Any, user_id: int) -> None:
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()


def create_invite(conn: Any, household_id: int, invited_by_user_id: int) -> str:
    token = secrets.token_urlsafe(24)
    ts = now()
    expires = (datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)).replace(
        microsecond=0
    ).isoformat()
    conn.execute(
        "INSERT INTO household_invites (token, household_id, invited_by, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (token, household_id, invited_by_user_id, ts, expires),
    )
    conn.commit()
    return token


def invite_info(conn: Any, token: str):
    row = conn.execute(
        """SELECT hi.household_id, hi.expires_at, hi.used_at, h.name AS household_name
           FROM household_invites hi JOIN households h ON h.id = hi.household_id
           WHERE hi.token = ?""",
        (token,),
    ).fetchone()
    if not row:
        raise AuthError("invite_invalid")
    if row["used_at"]:
        raise AuthError("invite_used")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        raise AuthError("invite_expired")
    return row


def accept_invite(conn: Any, token: str, email: str, password: str) -> str:
    row = invite_info(conn, token)
    household_id = row["household_id"]

    email = email.strip().lower()
    if not email or "@" not in email:
        raise AuthError("invalid_email")
    _check_password_strength(password)

    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        raise AuthError("email_taken")

    ts = now()
    cur = conn.execute(
        "INSERT INTO users (household_id, email, password_hash, created_at, "
        "failed_attempts, locked_until) VALUES (?, ?, ?, ?, 0, NULL)",
        (household_id, email, hash_password(password), ts),
    )
    user_id = cur.lastrowid
    conn.execute(
        "UPDATE household_invites SET used_at = ?, used_by = ? WHERE token = ?",
        (ts, user_id, token),
    )
    conn.commit()

    return _create_session(conn, user_id, household_id)


def list_members(conn: Any, household_id: int):
    return conn.execute(
        "SELECT id, email, created_at FROM users WHERE household_id = ? ORDER BY created_at",
        (household_id,),
    ).fetchall()


def _forget_user(conn: Any, user_id: int) -> None:
    """Remove one person: their login, sessions, reset links and the invites they sent
    (cascades), plus their Taste Lab answers. An invite they accepted keeps its row, without them."""
    conn.execute("UPDATE household_invites SET used_by = NULL WHERE used_by = ?", (user_id,))
    taste = conn.execute("SELECT to_regclass('taste_people') IS NOT NULL AS present").fetchone()
    if taste and taste["present"]:
        account = str(user_id)
        conn.execute(
            """DELETE FROM taste_events WHERE session_id IN (
                 SELECT s.id FROM taste_sessions s JOIN taste_people p ON p.id = s.person_id
                 WHERE p.account_id = ?)""",
            (account,),
        )
        conn.execute(
            "DELETE FROM taste_sessions WHERE person_id IN (SELECT id FROM taste_people WHERE account_id = ?)",
            (account,),
        )
        conn.execute("DELETE FROM taste_people WHERE account_id = ?", (account,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def _delete_household(conn: Any, household_id: int) -> None:
    """Everything a household owns. Most tables cascade from households; plans, the pantry and
    the household's own recipes don't, so they go first."""
    own = "SELECT id FROM recipes WHERE household_id = ?"
    # Another household's copy of one of these recipes keeps its copy, just not the link.
    conn.execute(f"UPDATE recipes SET parent_recipe_id = NULL WHERE parent_recipe_id IN ({own}) AND "
                 "(household_id IS NULL OR household_id <> ?)", (household_id, household_id))
    conn.execute("DELETE FROM plans WHERE household_id = ?", (household_id,))  # slots, grocery, prep cascade
    conn.execute(f"DELETE FROM plan_slots WHERE recipe_id IN ({own})", (household_id,))
    conn.execute("DELETE FROM pantry_items WHERE household_id = ?", (household_id,))
    conn.execute("UPDATE recipes SET parent_recipe_id = NULL WHERE household_id = ?", (household_id,))
    conn.execute("DELETE FROM recipes WHERE household_id = ?", (household_id,))
    conn.execute("DELETE FROM households WHERE id = ?", (household_id,))


def delete_account(conn: Any, user_id: int, password: str) -> bool:
    """Delete this account after checking its password (App Store guideline 5.1.1(v), #65).

    The last member takes the household and its whole kitchen with them. If others remain, the
    household stays theirs and only this person is removed. Returns True when the household
    was deleted too.
    """
    row = conn.execute(
        "SELECT household_id, password_hash FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not row or not verify_password(password or "", row["password_hash"]):
        raise AuthError("wrong_password")
    household_id = row["household_id"]
    others = conn.execute(
        "SELECT COUNT(*) AS n FROM users WHERE household_id = ? AND id <> ?", (household_id, user_id)
    ).fetchone()["n"]
    try:
        _forget_user(conn, user_id)
        if not others:
            _delete_household(conn, household_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return not others


def remove_member(conn: Any, household_id: int, target_user_id: int) -> None:
    members = list_members(conn, household_id)
    if len(members) <= 1:
        raise AuthError("last_member")
    row = conn.execute(
        "SELECT id FROM users WHERE id = ? AND household_id = ?",
        (target_user_id, household_id),
    ).fetchone()
    if not row:
        raise AuthError("not_found")
    # An accepted invite points at this person and would block a plain delete.
    _forget_user(conn, target_user_id)
    conn.commit()


def session_info(conn: Any, token: Optional[str]):
    if not token:
        return None
    row = conn.execute(
        """SELECT s.user_id, s.household_id, s.expires_at, u.email
           FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token = ?""",
        (token,),
    ).fetchone()
    if not row:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        return None
    return row


def household_for_token(conn: Any, token: Optional[str]) -> Optional[int]:
    row = session_info(conn, token)
    return row["household_id"] if row else None


def _create_session(conn: Any, user_id: int, household_id: int) -> str:
    token = secrets.token_urlsafe(32)
    ts = now()
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)).replace(
        microsecond=0
    ).isoformat()
    conn.execute(
        "INSERT INTO sessions (token, user_id, household_id, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (token, user_id, household_id, ts, expires),
    )
    conn.commit()
    return token
