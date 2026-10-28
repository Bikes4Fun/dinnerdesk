"""Password hashing + session tokens. Stdlib only (hashlib/secrets)."""

from __future__ import annotations

import json
import re
import hashlib
import os
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.db.database import now

PBKDF2_ITERATIONS = 600_000
SESSION_TTL_DAYS = 30
SESSION_COOKIE = "wp_session"

def is_admin(row) -> bool:
    """Can use the admin tools: the super admin, or an account they made an admin."""
    return row is not None and (is_admin_email(row["email"]) or bool(row["site_admin"]))


def is_admin_email(email: str | None) -> bool:
    """The super admin: the ADMIN_EMAIL account."""
    admin = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    if not email or not admin:
        return False
    return email.strip().lower() == admin

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
INVITE_TTL_DAYS = 7
RESET_TTL_MINUTES = 60
RESET_MAX_PER_HOUR = 3
VERIFY_TTL_HOURS = 24
LAST_SEEN_MINUTES = 5


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


def _lock_membership(conn):
    # Membership changes are rare. Serialize them so concurrent joins/deletions cannot
    # leave accounts in a household being deleted or bypass successor checks.
    conn.execute("SELECT pg_advisory_xact_lock(184732901)")


# A username stands in for an email for people who'd rather not share one. It lives in the same
# column; it can't contain "@", so it never collides with an email. Without an email there's no
# password reset, so a forgotten password can't be recovered.
USERNAME = re.compile(r"[a-z0-9._-]{3,30}")


def login_name(raw: str) -> str:
    """An email or username, normalized. Raises invalid_email / invalid_username."""
    name = (raw or "").strip().lower()
    if "@" in name:
        return name
    if not USERNAME.fullmatch(name):
        raise AuthError("invalid_username" if name else "invalid_email")
    return name


def has_email(name: str | None) -> bool:
    return bool(name) and "@" in name


def _name_taken(conn: Any, name: str) -> bool:
    """A sign-in name is taken if any account uses it as its login or its recovery email."""
    return conn.execute(
        "SELECT 1 FROM users WHERE email = ? OR recovery_email = ?", (name, name)
    ).fetchone() is not None


def reset_address(row) -> Optional[str]:
    """Where this account's reset links go: its login email, else its recovery email."""
    return row["email"] if has_email(row["email"]) else row["recovery_email"]


def _taken_by_other(conn: Any, name: str, user_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM users WHERE (email = ? OR recovery_email = ?) AND id <> ?", (name, name, user_id)
    ).fetchone() is not None


def signup(conn: Any, email: str, password: str, household_name: str, guest_household_id: int | None = None) -> str:
    _lock_membership(conn)
    email = login_name(email)
    _check_password_strength(password)

    if _name_taken(conn, email):
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
    conn.execute("UPDATE users SET household_role = 'owner' WHERE id = ?", (user_id,))
    conn.commit()

    return _create_session(conn, user_id, household_id)


def login(conn: Any, email: str, password: str) -> str:
    row = _authenticate(conn, email, password)
    return _create_session(conn, row["id"], row["household_id"])


def _authenticate(conn: Any, email: str, password: str):
    """Check credentials (with lockout) and return the user row; no session is created."""
    email = email.strip().lower()
    row = conn.execute(
        "SELECT id, household_id, password_hash, failed_attempts, locked_until "
        "FROM users WHERE email = ? OR recovery_email = ?",
        (email, email),
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

    return row


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


def reset_address_for(conn: Any, name: str) -> Optional[str]:
    """The reset address for this email or username, or None (unknown, or no email on file)."""
    name = (name or "").strip().lower()
    row = conn.execute(
        "SELECT email, recovery_email FROM users WHERE email = ? OR recovery_email = ?", (name, name)
    ).fetchone()
    return reset_address(row) if row else None


def start_password_reset(conn: Any, email: str) -> Optional[str]:
    """Make a one-time reset token for this email or username, or None (unknown, no email on file,
    or too many asks).

    Callers must answer the same way either way, so nobody can probe which emails have accounts.
    """
    email = (email or "").strip().lower()
    row = conn.execute(
        "SELECT id, email, recovery_email FROM users WHERE email = ? OR recovery_email = ?", (email, email)
    ).fetchone()
    if not row or not reset_address(row):
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


def start_email_verification(conn: Any, user_id: int, email: str) -> Optional[str]:
    """Make a one-time link that confirms `email` for this account, or None after too many asks.

    An email account's login becomes the address; a username account keeps its username and
    gets the address as its recovery email. Nothing changes until the link is opened, so a typo
    never locks anyone out. Raises invalid_email / email_taken.
    """
    email = login_name(email)
    if not has_email(email):
        raise AuthError("invalid_email")
    if _taken_by_other(conn, email, user_id):
        raise AuthError("email_taken")
    since = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0).isoformat()
    recent = conn.execute(
        "SELECT COUNT(*) AS c FROM email_verifications WHERE user_id = ? AND created_at > ?",
        (user_id, since),
    ).fetchone()["c"]
    if recent >= RESET_MAX_PER_HOUR:
        return None
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=VERIFY_TTL_HOURS)).replace(
        microsecond=0
    ).isoformat()
    conn.execute(
        "INSERT INTO email_verifications (token_hash, user_id, email, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (_reset_hash(token), user_id, email, now(), expires),
    )
    conn.commit()
    return token


def finish_email_verification(conn: Any, token: str) -> str:
    """Open a confirm link: the address becomes this account's login (or, for a username
    account, its recovery email), marked verified."""
    _lock_membership(conn)
    row = conn.execute(
        "SELECT user_id, email, expires_at, used_at FROM email_verifications WHERE token_hash = ?",
        (_reset_hash(token or ""),),
    ).fetchone()
    if not row or row["used_at"]:
        raise AuthError("verify_invalid")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        raise AuthError("verify_expired")
    if _taken_by_other(conn, row["email"], row["user_id"]):
        raise AuthError("email_taken")
    user = _member(conn, row["user_id"])
    column = "email" if has_email(user["email"]) else "recovery_email"
    conn.execute(
        f"UPDATE users SET {column} = ?, email_verified_at = ? WHERE id = ?",
        (row["email"], now(), row["user_id"]),
    )
    # Older links (to this or a mistyped address) stop working.
    conn.execute(
        "UPDATE email_verifications SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
        (now(), row["user_id"]),
    )
    conn.commit()
    return row["email"]


def _check_password(conn: Any, user_id: int, password: str) -> None:
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        raise AuthError("wrong_password")


def _close_verifications(conn: Any, user_id: int) -> None:
    conn.execute(
        "UPDATE email_verifications SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
        (now(), user_id),
    )


def use_username(conn: Any, user_id: int, password: str, username: str) -> None:
    """Swap the account's email for a username (removes the email). Needs the password."""
    _check_password(conn, user_id, password)
    name = login_name(username)
    if has_email(name):
        raise AuthError("invalid_username")
    if _taken_by_other(conn, name, user_id):
        raise AuthError("email_taken")
    conn.execute(
        "UPDATE users SET email = ?, recovery_email = NULL, email_verified_at = NULL WHERE id = ?",
        (name, user_id),
    )
    _close_verifications(conn, user_id)
    conn.commit()


def remove_recovery_email(conn: Any, user_id: int, password: str) -> None:
    """Drop a username account's recovery email. Needs the password."""
    _check_password(conn, user_id, password)
    conn.execute("UPDATE users SET recovery_email = NULL, email_verified_at = NULL WHERE id = ?", (user_id,))
    _close_verifications(conn, user_id)
    conn.commit()


def logout(conn: Any, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()


def logout_everywhere(conn: Any, user_id: int) -> None:
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()


def create_invite(conn: Any, household_id: int, invited_by_user_id: int) -> str:
    _lock_membership(conn)
    actor = _member(conn, invited_by_user_id)
    if actor["household_id"] != household_id:
        raise AuthError("household_forbidden")
    if not reset_address(actor):
        raise AuthError("email_required_to_invite")
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


def accept_invite(conn: Any, token: str, email: str, password: str, existing: bool = False) -> str:
    if existing:
        # Someone who already has an account signs in and moves into the inviting household.
        invite = invite_info(conn, token)
        user = _authenticate(conn, email, password)
        if user["household_id"] != invite["household_id"]:
            join_household(conn, user["id"], token)
        return _create_session(conn, user["id"], invite["household_id"])

    _lock_membership(conn)
    row = invite_info(conn, token)
    household_id = row["household_id"]

    email = login_name(email)
    _check_password_strength(password)

    if _name_taken(conn, email):
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
        "SELECT id, email, created_at, household_role FROM users WHERE household_id = ? ORDER BY created_at",
        (household_id,),
    ).fetchall()


def _forget_user(conn: Any, user_id: int) -> None:
    """Remove one person: their login, sessions, reset links and the invites they sent
    (cascades), plus identifying Taste Lab records after preserving unlinked votes. An invite they accepted keeps its row, without them."""
    conn.execute("UPDATE household_invites SET used_by = NULL WHERE used_by = ?", (user_id,))
    conn.execute("UPDATE admin_actions SET target_label = 'deleted account' WHERE target_user_id = ?", (user_id,))
    conn.execute("UPDATE admin_actions SET admin_label = 'deleted account' WHERE admin_user_id = ?", (user_id,))
    _forget_taste(conn, str(user_id), "individual")
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def _forget_taste(conn: Any, account: str, scope: str) -> None:
    """One Taste Lab account's identifying records, after keeping its votes unlinked."""
    _archive_taste(conn, account, scope)
    present = conn.execute("SELECT to_regclass('taste_people') IS NOT NULL AS present").fetchone()
    if not present or not present["present"]:
        return
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


def _archive_taste(conn: Any, account: str | list[str], scope: str) -> None:
    present = conn.execute("SELECT to_regclass('taste_people') IS NOT NULL AS present").fetchone()
    if not present or not present["present"]:
        return
    accounts = [account] if isinstance(account, str) else account
    if not accounts:
        return
    marks = ", ".join("?" for _ in accounts)
    rows = conn.execute(f"""SELECT e.body, p.account_id FROM taste_events e
        JOIN taste_sessions s ON s.id = e.session_id JOIN taste_people p ON p.id = s.person_id
        WHERE p.account_id IN ({marks}) AND e.kind = 'snapshot' ORDER BY e.id DESC""", accounts).fetchall()
    # Latest vote per meal per person. Account IDs exist only in this transaction.
    histories = {}
    for row in rows:
        votes = histories.setdefault(row["account_id"], {})
        for swipe in json.loads(row["body"]).get("swipes", []):
            recipe = swipe.get("recipe_id")
            if recipe is not None and isinstance(swipe.get("liked"), bool):
                votes.setdefault(str(recipe), "like" if swipe["liked"] else "pass")
    retained = {}
    for votes in histories.values():
        for recipe, vote in votes.items():
            if scope == "household":
                counts = retained.setdefault(recipe, {"like": 0, "pass": 0})
                counts[vote] += 1
            else:
                retained[recipe] = vote
    if retained:
        conn.execute("INSERT INTO anonymous_taste_history (scope, votes_json) VALUES (?, ?)",
                     (scope, json.dumps(retained)))


def _delete_household(conn: Any, household_id: int) -> None:
    """Everything a household owns. Most tables cascade from households; plans, the pantry and
    the household's own recipes don't, so they go first."""
    _forget_taste(conn, f"guest:{household_id}", "household")
    _archive_ratings(conn, household_id)
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


def _archive_ratings(conn: Any, household_id: int) -> None:
    ratings = conn.execute("SELECT recipe_id, rating FROM household_meal_ratings WHERE household_id = ?", (household_id,)).fetchall()
    if ratings:
        conn.execute("INSERT INTO anonymous_taste_history (scope, votes_json) VALUES ('household', ?)",
                     (json.dumps({str(r["recipe_id"]): r["rating"] for r in ratings}),))


def delete_guest_kitchen(conn: Any, household_id: int) -> None:
    """A guest's "Delete my kitchen" (#101): the kitchen and its Taste Lab answers go from the
    server, not just the cookie. A household with an account in it is never a guest's."""
    if conn.execute("SELECT id FROM users WHERE household_id = ?", (household_id,)).fetchone():
        raise AuthError("household_forbidden")
    try:
        _delete_household(conn, household_id)  # guest_sessions cascade
        conn.commit()
    except Exception:
        conn.rollback()
        raise


CLEARABLE = ("taste_lab", "meal_ratings", "prep_votes")


def clear_data(conn: Any, household_id: int, user_id: int | None, kinds: list[str]) -> None:
    """Clear parts of your data without deleting the account (#101). Taste Lab history is your
    own; meal ratings and prep votes belong to the household, so only its creator or an admin
    (or a guest, alone in their kitchen) can clear them. Votes are kept unlinked, as on delete."""
    if not kinds or any(kind not in CLEARABLE for kind in kinds):
        raise AuthError("invalid_clear")
    if user_id is not None and {"meal_ratings", "prep_votes"} & set(kinds):
        if _member(conn, user_id)["household_role"] not in ("owner", "admin"):
            raise AuthError("household_forbidden")
    try:
        if "taste_lab" in kinds:
            if user_id is None:
                _forget_taste(conn, f"guest:{household_id}", "household")
            else:
                _forget_taste(conn, str(user_id), "individual")
        if "meal_ratings" in kinds:
            _archive_ratings(conn, household_id)
            conn.execute("DELETE FROM household_meal_ratings WHERE household_id = ?", (household_id,))
        if "prep_votes" in kinds:
            conn.execute("DELETE FROM prep_step_feedback WHERE household_id = ?", (household_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def delete_account(conn: Any, user_id: int, password: str) -> bool:
    """Delete this account after checking its password (App Store guideline 5.1.1(v), #65).

    The last member takes the household and its whole kitchen with them. If others remain, the
    household stays theirs and only this person is removed. Returns True when the household
    was deleted too.
    """
    _lock_membership(conn)
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
        _require_successor(conn, user_id)
        _forget_user(conn, user_id)
        if not others:
            _delete_household(conn, household_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return not others


def _member(conn, user_id):
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise AuthError("not_found")
    return row


def _require_successor(conn, user_id):
    user = _member(conn, user_id)
    others = conn.execute("SELECT COUNT(*) AS n FROM users WHERE household_id = ? AND id <> ?",
                          (user["household_id"], user_id)).fetchone()["n"]
    if user["household_role"] == "owner" and others:
        raise AuthError("successor_required")


def _solo(conn, user_id):
    cur = conn.execute("INSERT INTO households (name, prefs_json, created_at) VALUES ('My household', '{}', ?)", (now(),))
    hid = cur.lastrowid
    conn.execute("DELETE FROM household_invites WHERE invited_by = ? AND used_at IS NULL", (user_id,))
    conn.execute("UPDATE users SET household_id = ?, household_role = 'owner' WHERE id = ?", (hid, user_id))
    conn.execute("UPDATE sessions SET household_id = ? WHERE user_id = ?", (hid, user_id))
    return hid


def manage_member(conn, actor_id, target_id, role):
    _lock_membership(conn)
    actor, target = _member(conn, actor_id), _member(conn, target_id)
    if actor["household_id"] != target["household_id"] or actor["household_role"] != "owner":
        raise AuthError("household_forbidden")
    if target_id == actor_id or role not in ("owner", "admin", "member"):
        raise AuthError("invalid_role")
    if role == "owner":
        conn.execute("UPDATE users SET household_role = 'admin' WHERE id = ?", (actor_id,))
    conn.execute("UPDATE users SET household_role = ? WHERE id = ?", (role, target_id))
    conn.commit()


def leave_household(conn, user_id):
    _lock_membership(conn)
    user = _member(conn, user_id)
    _require_successor(conn, user_id)
    old = user["household_id"]
    _solo(conn, user_id)
    if not conn.execute("SELECT id FROM users WHERE household_id = ?", (old,)).fetchone():
        _delete_household(conn, old)
    conn.commit()


def delete_household(conn, user_id, password):
    _lock_membership(conn)
    user = _member(conn, user_id)
    if user["household_role"] not in ("owner", "admin"):
        raise AuthError("household_forbidden")
    if not verify_password(password, user["password_hash"]):
        raise AuthError("wrong_password")
    hid = user["household_id"]
    try:
        members = list_members(conn, hid)
        _archive_taste(conn, [str(member["id"]) for member in members], "household")
        for member in members:
            _solo(conn, member["id"])
        _delete_household(conn, hid)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def join_household(conn, user_id, token):
    _lock_membership(conn)
    invite = invite_info(conn, token)
    user = _member(conn, user_id)
    if user["household_id"] == invite["household_id"]:
        raise AuthError("already_member")
    _require_successor(conn, user_id)
    old = user["household_id"]
    conn.execute("UPDATE users SET household_id = ?, household_role = 'member' WHERE id = ?", (invite["household_id"], user_id))
    conn.execute("UPDATE sessions SET household_id = ? WHERE user_id = ?", (invite["household_id"], user_id))
    conn.execute("UPDATE household_invites SET used_at = ?, used_by = ? WHERE token = ?", (now(), user_id, token))
    if not conn.execute("SELECT id FROM users WHERE household_id = ?", (old,)).fetchone():
        _delete_household(conn, old)
    conn.commit()


def remove_member(conn: Any, household_id: int, target_user_id: int, actor_id: int) -> None:
    _lock_membership(conn)
    actor, target = _member(conn, actor_id), _member(conn, target_user_id)
    if actor["household_id"] != household_id or actor["household_role"] not in ("owner", "admin") or target["household_id"] != household_id or target["household_role"] == "owner":
        raise AuthError("household_forbidden")
    _solo(conn, target_user_id)
    conn.commit()


# Admin user management (/admin/users). These skip the password an account's owner would need.

def session_id(token: str) -> str:
    """A session's stand-in on the admin page, so its token never leaves the server."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def describe_device(user_agent: str, app: str = "") -> str:
    """A short name for what signed in: "iOS app 1.2 (34)", "Safari on Mac"."""
    if app.startswith("ios "):
        return f"iOS app {app[4:]}"
    ua = user_agent or ""
    browser = next((name for key, name in (("Edg/", "Edge"), ("Firefox/", "Firefox"), ("CriOS/", "Chrome"),
                    ("Chrome/", "Chrome"), ("Safari/", "Safari")) if key in ua), "")
    system = next((name for key, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"),
                   ("Mac OS X", "Mac"), ("Windows", "Windows"), ("Linux", "Linux")) if key in ua), "")
    return " on ".join(part for part in (browser, system) if part) or ua[:60]


def record_device(conn: Any, token: str, user_agent: str, app: str = "") -> None:
    conn.execute("UPDATE sessions SET device = ? WHERE token = ?", (describe_device(user_agent, app), token))
    conn.commit()


def admin_send_reset(conn: Any, user_id: int) -> tuple[str, str] | None:
    """A reset token and where to send it, or None (no email on file, or too many this hour)."""
    user = _member(conn, user_id)
    to = reset_address(user)
    token = start_password_reset(conn, user["email"]) if to else None
    return (to, token) if token else None


def admin_resend_confirmation(conn: Any, user_id: int) -> tuple[str, str] | None:
    """A confirm token for the account's unconfirmed address and the address, or None after too
    many this hour. Raises invalid_email when there's no address to confirm."""
    user = _member(conn, user_id)
    to = reset_address(user)
    if not to:
        raise AuthError("invalid_email")
    token = start_email_verification(conn, user_id, to)
    return (to, token) if token else None


def admin_set_site_admin(conn: Any, user_id: int, on: bool) -> None:
    """Make an account an admin, or not. The super admin is always one."""
    user = _member(conn, user_id)
    if is_admin_email(user["email"]):
        raise AuthError("super_admin")
    conn.execute("UPDATE users SET site_admin = ? WHERE id = ?", (int(on), user_id))
    conn.commit()


def log_admin_action(conn: Any, admin, target_user_id: int, action: str, detail: str = "") -> None:
    """Record what an admin did to an account (never a password or token)."""
    target = conn.execute("SELECT email FROM users WHERE id = ?", (target_user_id,)).fetchone()
    conn.execute(
        "INSERT INTO admin_actions (admin_user_id, admin_label, target_user_id, target_label, action, detail, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (admin["user_id"], admin["email"], target_user_id if target else None, target["email"] if target else "",
         action, detail, now()),
    )
    conn.commit()


def admin_set_password(conn: Any, user_id: int, password: str) -> None:
    """Set a password for someone, unlock them, close their reset links and sign them out."""
    _member(conn, user_id)
    _check_password_strength(password)
    conn.execute(
        "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
        (hash_password(password), user_id),
    )
    conn.execute("UPDATE password_resets SET used_at = ? WHERE user_id = ? AND used_at IS NULL", (now(), user_id))
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()


def admin_unlock(conn: Any, user_id: int) -> None:
    _member(conn, user_id)
    conn.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?", (user_id,))
    conn.commit()


def admin_set_login(conn: Any, user_id: int, name: str) -> None:
    """Change the email or username someone signs in with. A new email is unconfirmed, and an
    email login drops the recovery email (resets go to the login itself)."""
    _lock_membership(conn)
    user = _member(conn, user_id)
    name = login_name(name)
    if _taken_by_other(conn, name, user_id):
        raise AuthError("email_taken")
    if has_email(name):
        conn.execute("UPDATE users SET email = ?, recovery_email = NULL, email_verified_at = NULL WHERE id = ?",
                     (name, user_id))
    elif has_email(user["email"]):
        conn.execute("UPDATE users SET email = ?, email_verified_at = NULL WHERE id = ?", (name, user_id))
    else:
        conn.execute("UPDATE users SET email = ? WHERE id = ?", (name, user_id))
    _close_verifications(conn, user_id)
    conn.commit()


def admin_set_recovery_email(conn: Any, user_id: int, email: str) -> None:
    """Set (unconfirmed) or, when blank, remove a username account's recovery email."""
    _lock_membership(conn)
    user = _member(conn, user_id)
    if has_email(user["email"]):
        raise AuthError("invalid_username")
    email = (email or "").strip().lower()
    if email:
        if not has_email(email):
            raise AuthError("invalid_email")
        if _taken_by_other(conn, email, user_id):
            raise AuthError("email_taken")
    conn.execute("UPDATE users SET recovery_email = ?, email_verified_at = NULL WHERE id = ?", (email or None, user_id))
    _close_verifications(conn, user_id)
    conn.commit()


def admin_end_sessions(conn: Any, user_id: int, session: str | None = None) -> None:
    """Sign someone out of one session (by its session_id) or, with none given, everywhere."""
    _member(conn, user_id)
    for row in conn.execute("SELECT token FROM sessions WHERE user_id = ?", (user_id,)).fetchall():
        if session is None or session_id(row["token"]) == session:
            conn.execute("DELETE FROM sessions WHERE token = ?", (row["token"],))
    conn.commit()


def admin_reset_taste(conn: Any, user_id: int) -> None:
    """Clear someone's Taste Lab history. Votes are kept unlinked, as when they clear it."""
    _member(conn, user_id)
    try:
        _forget_taste(conn, str(user_id), "individual")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def admin_move_user(conn: Any, user_id: int, household_id: int | None) -> None:
    """Move someone into another household (as a member, or owner if it has no accounts), or
    with None into a new one of their own. An owner with others still at home needs a new owner
    first. A household left with no accounts is deleted, as when its last member leaves."""
    _lock_membership(conn)
    user = _member(conn, user_id)
    _require_successor(conn, user_id)
    old = user["household_id"]
    if household_id is None:
        _solo(conn, user_id)
    else:
        if household_id == old:
            raise AuthError("already_member")
        if not conn.execute("SELECT 1 FROM households WHERE id = ?", (household_id,)).fetchone():
            raise AuthError("not_found")
        empty = not conn.execute("SELECT 1 FROM users WHERE household_id = ?", (household_id,)).fetchone()
        conn.execute("DELETE FROM household_invites WHERE invited_by = ? AND used_at IS NULL", (user_id,))
        conn.execute("UPDATE users SET household_id = ?, household_role = ? WHERE id = ?",
                     (household_id, "owner" if empty else "member", user_id))
        conn.execute("UPDATE sessions SET household_id = ? WHERE user_id = ?", (household_id, user_id))
    if not conn.execute("SELECT id FROM users WHERE household_id = ?", (old,)).fetchone():
        _delete_household(conn, old)
    conn.commit()


def admin_set_role(conn: Any, user_id: int, role: str) -> None:
    """Change someone's household role. Making someone owner makes the old owner an admin; the
    owner can't step down without naming a new one."""
    _lock_membership(conn)
    user = _member(conn, user_id)
    if role not in ("owner", "admin", "member"):
        raise AuthError("invalid_role")
    if user["household_role"] == "owner" and role != "owner":
        raise AuthError("successor_required")
    if role == "owner":
        conn.execute("UPDATE users SET household_role = 'admin' WHERE household_id = ? AND household_role = 'owner'",
                     (user["household_id"],))
    conn.execute("UPDATE users SET household_role = ? WHERE id = ?", (role, user_id))
    conn.commit()


def session_info(conn: Any, token: Optional[str]):
    if not token:
        return None
    row = conn.execute(
        """SELECT s.user_id, s.household_id, s.expires_at, u.email, u.recovery_email, u.email_verified_at,
                  u.last_seen_at, u.site_admin
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
    # Last seen, written at most every few minutes so most requests don't write.
    seen = (datetime.now(timezone.utc) - timedelta(minutes=LAST_SEEN_MINUTES)).replace(microsecond=0).isoformat()
    if not row["last_seen_at"] or row["last_seen_at"] < seen:
        conn.execute("UPDATE users SET last_seen_at = ? WHERE id = ?", (now(), row["user_id"]))
        conn.commit()
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
