from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import SESSION_COOKIE
from app.db.database import connect, init_db
from app.main import create_app


def _client(tmp_path: Path) -> TestClient:
    db = connect()
    init_db(db)
    db.close()
    return TestClient(create_app())


def test_signup_login_me_logout(tmp_path):
    with _client(tmp_path) as client:
        res = client.post(
            "/api/auth/signup",
            json={
                "email": "you@example.com",
                "password": "correct horse battery staple",
                "household_name": "Our house",
            },
        )
        assert res.status_code == 200
        assert SESSION_COOKIE in res.cookies
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["household_id"] == 1
        assert me.json()["email"] == "you@example.com"
        assert me.json()["admin"] is False
        client.post("/api/auth/logout")
        assert client.get("/api/auth/me").status_code == 401
        bad = client.post(
            "/api/auth/login",
            json={"email": "you@example.com", "password": "wrongwrong"},
        )
        assert bad.status_code == 401
        ok = client.post(
            "/api/auth/login",
            json={
                "email": "you@example.com",
                "password": "correct horse battery staple",
            },
        )
        assert ok.status_code == 200
        assert client.get("/api/auth/me").status_code == 200


def test_guest_access_remains_available_when_auth_required_env_set(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    with _client(tmp_path) as client:
        res = client.get("/api/auth/status")
        assert res.json()["required"] is False
        assert client.get("/api/recipes").status_code == 200
        client.post(
            "/api/auth/signup",
            json={
                "email": "need@example.com",
                "password": "correct horse battery staple",
                "household_name": "House",
            },
        )
        assert client.get("/api/recipes").status_code == 200


def test_auth_status_not_required_by_default(tmp_path):
    with _client(tmp_path) as client:
        res = client.get("/api/auth/status")
        assert res.status_code == 200
        body = res.json()
        assert body["required"] is False
        assert body["authenticated"] is False
        assert body["admin"] is False


def test_auth_required_ignores_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/dinnerdesk")
    monkeypatch.delenv("AUTH_REQUIRED", raising=False)
    from app.deps import auth_required

    assert auth_required() is False


def test_admin_flag_for_tagged_emails(tmp_path):
    with _client(tmp_path) as client:
        client.post(
            "/api/auth/signup",
            json={
                "email": "garrett.deanna@gmail.com",
                "password": "correct horse battery staple",
                "household_name": "Dev",
            },
        )
        me = client.get("/api/auth/me").json()
        assert me["admin"] is True
        assert client.get("/api/auth/status").json()["admin"] is True


def test_lockout_after_five_failures(tmp_path):
    with _client(tmp_path) as client:
        client.post(
            "/api/auth/signup",
            json={
                "email": "lock@example.com",
                "password": "correct horse battery staple",
                "household_name": "House",
            },
        )
        client.post("/api/auth/logout")
        for _ in range(5):
            bad = client.post(
                "/api/auth/login",
                json={"email": "lock@example.com", "password": "wrongwrong"},
            )
            assert bad.status_code == 401
        locked = client.post(
            "/api/auth/login",
            json={"email": "lock@example.com", "password": "wrongwrong"},
        )
        assert locked.status_code == 423
        assert locked.json()["detail"] == "account_locked"


def test_change_password_and_logout_everywhere(tmp_path):
    with _client(tmp_path) as client:
        client.post(
            "/api/auth/signup",
            json={
                "email": "pw@example.com",
                "password": "oldoldold",
                "household_name": "House",
            },
        )
        changed = client.post(
            "/api/auth/change-password",
            json={"current_password": "oldoldold", "new_password": "newnewnew"},
        )
        assert changed.status_code == 200
        assert client.get("/api/auth/me").status_code == 200
        client.post("/api/auth/logout-everywhere")
        assert client.get("/api/auth/me").status_code == 401
        ok = client.post(
            "/api/auth/login",
            json={"email": "pw@example.com", "password": "newnewnew"},
        )
        assert ok.status_code == 200


def test_invite_joins_same_household(tmp_path):
    with _client(tmp_path) as client:
        client.post(
            "/api/auth/signup",
            json={
                "email": "owner@example.com",
                "password": "correct horse battery staple",
                "household_name": "The Martins",
            },
        )
        hid = client.get("/api/auth/me").json()["household_id"]
        only = client.get("/api/household/members").json()["members"]
        assert len(only) == 1
        gone = client.delete(f"/api/household/members/{only[0]['id']}")
        assert gone.status_code == 400
        token = client.post("/api/household/invites").json()["token"]
        preview = client.get(f"/api/household/invites/{token}")
        assert preview.json()["household_name"] == "The Martins"
        client.post("/api/auth/logout")
        accepted = client.post(
            "/api/household/accept-invite",
            json={
                "token": token,
                "email": "guest@example.com",
                "password": "guestguest",
            },
        )
        assert accepted.status_code == 200
        assert client.get("/api/auth/me").json()["household_id"] == hid
        reused = client.post(
            "/api/household/accept-invite",
            json={
                "token": token,
                "email": "other@example.com",
                "password": "guestguest",
            },
        )
        assert reused.status_code == 400
        assert reused.json()["detail"] == "invite_used"


def test_delete_account_keeps_household_for_others_then_deletes_it(tmp_path):
    owner = {"email": "owner@example.com", "password": "correct horse battery staple"}
    with _client(tmp_path) as client:
        client.post("/api/auth/signup", json={**owner, "household_name": "The Martins"})
        hid = client.get("/api/auth/me").json()["household_id"]
        token = client.post("/api/household/invites").json()["token"]
        client.post("/api/auth/logout")
        client.post(
            "/api/household/accept-invite",
            json={"token": token, "email": "guest@example.com", "password": "guestguest"},
        )

        wrong = client.post("/api/auth/delete-account", json={"password": "nope"})
        assert wrong.status_code == 400
        assert wrong.json()["detail"] == "wrong_password"

        # The invited member leaves; the household stays for the owner.
        left = client.post("/api/auth/delete-account", json={"password": "guestguest"})
        assert left.status_code == 200
        assert left.json()["household_deleted"] is False
        assert client.get("/api/auth/me").status_code == 401
        assert client.post("/api/auth/login", json={"email": "guest@example.com", "password": "guestguest"}).status_code != 200

        assert client.post("/api/auth/login", json=owner).status_code == 200
        assert client.get("/api/auth/me").json()["household_id"] == hid
        assert len(client.get("/api/household/members").json()["members"]) == 1

        # The last member takes the household with them.
        gone = client.post("/api/auth/delete-account", json={"password": owner["password"]})
        assert gone.status_code == 200
        assert gone.json()["household_deleted"] is True
        assert client.post("/api/auth/login", json=owner).status_code != 200
        client.post("/api/auth/signup", json={**owner, "household_name": "Again"})
        assert client.get("/api/auth/me").status_code == 200


def test_remove_member_who_joined_by_invite(tmp_path):
    with _client(tmp_path) as client:
        client.post(
            "/api/auth/signup",
            json={"email": "owner@example.com", "password": "correct horse battery staple", "household_name": "H"},
        )
        token = client.post("/api/household/invites").json()["token"]
        client.post("/api/auth/logout")
        client.post(
            "/api/household/accept-invite",
            json={"token": token, "email": "guest@example.com", "password": "guestguest"},
        )
        client.post("/api/auth/logout")
        client.post("/api/auth/login", json={"email": "owner@example.com", "password": "correct horse battery staple"})
        guest = [m for m in client.get("/api/household/members").json()["members"] if m["email"] == "guest@example.com"][0]
        assert client.delete(f"/api/household/members/{guest['id']}").status_code == 200


def test_guest_kitchens_are_private_persist_and_survive_stale_signin(tmp_path):
    from app.deps import GUEST_COOKIE
    with _client(tmp_path) as first, TestClient(create_app()) as second:
        first.cookies.set(SESSION_COOKIE, "expired-signin", domain="testserver.local", path="/")
        assert first.get("/api/auth/status").json()["authenticated"] is False
        assert GUEST_COOKIE in first.cookies
        a = first.get("/api/plans/current").json()
        b = second.get("/api/plans/current").json()
        assert a["id"] != b["id"]
        assert first.get("/api/plans/current").json()["id"] == a["id"]
        assert second.get(f"/api/plans/{a['id']}").status_code == 404
        assert first.put("/api/household", json={"prefs": {"family_portions": 7}}).status_code == 200
        assert second.get("/api/household").json()["prefs"].get("family_portions") != 7
        assert first.get("/api/plans/current").status_code == 200


def test_signup_keeps_guest_data_and_revokes_guest_cookie(tmp_path):
    from app.deps import GUEST_COOKIE
    with _client(tmp_path) as guest:
        plan = guest.get("/api/plans/current").json()
        cookie = guest.cookies.get(GUEST_COOKIE)
        guest.put("/api/household", json={"prefs": {"family_portions": 6}})
        assert guest.post("/api/auth/signup", json={"email": "keep@example.com", "password": "guestguest"}).status_code == 200
        assert guest.get("/api/plans/current").json()["id"] == plan["id"]
        assert guest.get("/api/household").json()["prefs"]["family_portions"] == 6
        with TestClient(create_app(), cookies={GUEST_COOKIE: cookie}) as old_guest:
            assert old_guest.get(f"/api/plans/{plan['id']}").status_code == 404


def test_guest_tastelab_votes_and_filters_persist(tmp_path):
    with _client(tmp_path) as guest, TestClient(create_app()) as other:
        guest.get("/api/auth/status")
        assert guest.post("/api/sessions", json={"anon_id": "test-anon-123", "id": "guest-test", "kind": "snapshot", "body": {"swipes": [{"recipe_id": "395", "liked": True}]}}).status_code == 200
        assert guest.get("/api/taste").json()["votes"] == [{"recipe_id": "395", "liked": True}]
        assert other.get("/api/taste").json()["votes"] == []
        assert guest.put("/api/household", json={"prefs": {"filters": {"diets": ["vegetarian"], "avoids": ["cilantro"]}}}).status_code == 200
        assert "vegetarian" in guest.get("/api/taste").json()["profile"]["diets"]
        assert "cilantro" in guest.get("/api/taste").json()["profile"]["dislikes"]
        guest.post("/api/auth/signup", json={"email": "taste@example.com", "password": "guestguest"})
        assert guest.get("/api/taste").json()["votes"] == [{"recipe_id": "395", "liked": True}]
