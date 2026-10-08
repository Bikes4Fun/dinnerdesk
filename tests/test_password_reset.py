"""Forgot-password flow: one-time, expiring, rate-limited links that keep household data."""

from datetime import datetime, timedelta, timezone

import pytest

from app.auth import (
    AuthError,
    finish_password_reset,
    login,
    signup,
    start_password_reset,
)
from app.db.database import connect, init_db


@pytest.fixture()
def conn(tmp_path):
    c = connect()
    init_db(c)
    signup(c, "Me@Example.com", "oldpassword1", "Home")
    yield c
    c.close()


def test_reset_sets_new_password_and_signs_out(conn):
    old_session = conn.execute("SELECT token FROM sessions").fetchone()["token"]
    token = start_password_reset(conn, " ME@example.com ")
    assert token
    session = finish_password_reset(conn, token, "newpassword9")
    assert session
    assert conn.execute("SELECT 1 FROM sessions WHERE token = ?", (old_session,)).fetchone() is None
    assert login(conn, "me@example.com", "newpassword9")
    with pytest.raises(AuthError):
        login(conn, "me@example.com", "oldpassword1")


def test_link_works_once(conn):
    token = start_password_reset(conn, "me@example.com")
    finish_password_reset(conn, token, "newpassword9")
    with pytest.raises(AuthError) as e:
        finish_password_reset(conn, token, "another12345")
    assert e.value.detail == "reset_invalid"


def test_new_password_invalidates_other_open_links(conn):
    first = start_password_reset(conn, "me@example.com")
    second = start_password_reset(conn, "me@example.com")
    finish_password_reset(conn, second, "newpassword9")
    with pytest.raises(AuthError):
        finish_password_reset(conn, first, "another12345")


def test_expired_link(conn):
    token = start_password_reset(conn, "me@example.com")
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(microsecond=0).isoformat()
    conn.execute("UPDATE password_resets SET expires_at = ?", (past,))
    conn.commit()
    with pytest.raises(AuthError) as e:
        finish_password_reset(conn, token, "newpassword9")
    assert e.value.detail == "reset_expired"


def test_unknown_email_and_bad_token(conn):
    assert start_password_reset(conn, "nobody@example.com") is None
    with pytest.raises(AuthError) as e:
        finish_password_reset(conn, "made-up", "newpassword9")
    assert e.value.detail == "reset_invalid"


def test_short_password_keeps_link_usable(conn):
    token = start_password_reset(conn, "me@example.com")
    with pytest.raises(AuthError) as e:
        finish_password_reset(conn, token, "short")
    assert e.value.detail == "password_too_short"
    assert finish_password_reset(conn, token, "newpassword9")


def test_rate_limit(conn):
    tokens = [start_password_reset(conn, "me@example.com") for _ in range(4)]
    assert all(tokens[:3]) and tokens[3] is None


def test_household_data_kept(conn):
    before = conn.execute("SELECT household_id FROM users").fetchone()["household_id"]
    finish_password_reset(conn, start_password_reset(conn, "me@example.com"), "newpassword9")
    assert conn.execute("SELECT household_id FROM users").fetchone()["household_id"] == before
