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
                "email": "admin@example.test",
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


def test_existing_account_accepts_invite_while_signed_out(tmp_path):
    guest = {"email": "guest@example.com", "password": "guestguest"}
    with _client(tmp_path) as client:
        client.post("/api/auth/signup", json={**guest, "household_name": "Guest solo"})
        old = client.get("/api/auth/me").json()["household_id"]
        client.post("/api/auth/logout")
        client.post("/api/auth/signup", json={"email": "owner@example.com", "password": "correct horse battery staple", "household_name": "The Martins"})
        hid = client.get("/api/auth/me").json()["household_id"]
        token = client.post("/api/household/invites").json()["token"]
        client.post("/api/auth/logout")

        taken = client.post("/api/household/accept-invite", json={**guest, "token": token})
        assert taken.json()["detail"] == "email_taken"
        wrong = client.post("/api/household/accept-invite", json={**guest, "password": "nopenope", "token": token, "existing": True})
        assert wrong.json()["detail"] == "invalid_credentials"
        joined = client.post("/api/household/accept-invite", json={**guest, "token": token, "existing": True})
        assert joined.status_code == 200
        assert client.get("/api/auth/me").json()["household_id"] == hid
        assert len(client.get("/api/household/members").json()["members"]) == 2
        assert old != hid
        reused = client.post("/api/household/accept-invite", json={**guest, "token": token, "existing": True})
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


def test_household_separation_roles_and_account_deletion(tmp_path):
    owner = {"email": "creator@example.com", "password": "correct horse battery staple"}
    guest = {"email": "member@example.com", "password": "memberpassword"}
    with _client(tmp_path) as client:
        client.post('/api/auth/signup', json={**owner, 'household_name': 'Shared'})
        owner_me = client.get('/api/auth/me').json()
        token = client.post('/api/household/invites').json()['token']
        client.post('/api/auth/logout')
        client.post('/api/household/accept-invite', json={**guest, 'token': token})
        member_me = client.get('/api/auth/me').json()
        assert client.post('/api/household/delete', json={'password': guest['password']}).status_code == 400
        assert client.delete(f"/api/household/members/{owner_me['user_id']}").status_code == 400
        assert client.post('/api/household/leave').status_code == 200
        assert client.get('/api/auth/me').json()['household_id'] != owner_me['household_id']
        client.post('/api/auth/logout')
        client.post('/api/auth/login', json=owner)
        token = client.post('/api/household/invites').json()['token']
        client.post('/api/auth/logout')
        client.post('/api/auth/login', json=guest)
        assert client.post('/api/household/join', json={'token': token}).status_code == 200
        client.post('/api/auth/logout')
        client.post('/api/auth/login', json=owner)
        assert client.post('/api/auth/delete-account', json={'password': owner['password']}).json()['detail'] == 'successor_required'
        assert client.post('/api/household/leave').json()['detail'] == 'successor_required'
        assert client.put(f"/api/household/members/{member_me['user_id']}/role", json={'role': 'admin'}).status_code == 200
        assert client.delete(f"/api/household/members/{member_me['user_id']}").status_code == 200
        client.post('/api/auth/logout')
        assert client.post('/api/auth/login', json=guest).status_code == 200
        assert client.get('/api/auth/me').json()['household_id'] != owner_me['household_id']
        client.post('/api/auth/logout')
        client.post('/api/auth/login', json=owner)
        token = client.post('/api/household/invites').json()['token']
        client.post('/api/auth/logout')
        client.post('/api/auth/login', json=guest)
        client.post('/api/household/join', json={'token': token})
        client.post('/api/auth/logout')
        client.post('/api/auth/login', json=owner)
        assert client.put(f"/api/household/members/{member_me['user_id']}/role", json={'role': 'owner'}).status_code == 200
        assert client.post('/api/household/delete', json={'password': 'wrong'}).status_code == 400
        assert client.post('/api/household/delete', json={'password': owner['password']}).status_code == 200
        owner_home = client.get('/api/auth/me').json()['household_id']
        client.post('/api/auth/logout')
        assert client.post('/api/auth/login', json=guest).status_code == 200
        assert client.get('/api/auth/me').json()['household_id'] not in (owner_home, owner_me['household_id'])


def test_deleted_account_retains_only_unlinked_votes(tmp_path):
    import json
    with _client(tmp_path) as client:
        client.post('/api/auth/signup', json={'email': 'history@example.com', 'password': 'historypassword'})
        me = client.get('/api/auth/me').json()
        from app.taste_lab import taste
        taste().init_db()
        with connect() as db:
            pid = db.execute("INSERT INTO taste_people (anon_id, account_id, created_at) VALUES (?, ?, ?) RETURNING id",
                             ('old-browser', str(me['user_id']), 'old-time')).fetchone()['id']
            db.execute("INSERT INTO taste_sessions (id, person_id, created_at, updated_at) VALUES (?, ?, ?, ?)", ('old-session', pid, 'old-time', 'old-time'))
            db.execute("INSERT INTO taste_events (session_id, t, kind, body) VALUES (?, ?, 'snapshot', ?)",
                       ('old-session', 'old-time', json.dumps({'id': 'old-session', 'email': 'history@example.com', 'swipes': [{'recipe_id': '42', 'liked': True, 'name': 'secret'}]})))
            db.commit()
        assert client.post('/api/auth/delete-account', json={'password': 'historypassword'}).status_code == 200
        with connect() as db:
            row = db.execute('SELECT * FROM anonymous_taste_history').fetchone()
            assert json.loads(row['votes_json']) == {'42': 'like'}
            assert row['scope'] == 'individual'
            assert not db.execute('SELECT id FROM taste_people').fetchone()
            assert not db.execute('SELECT id FROM taste_events').fetchone()


def test_creator_can_delete_account_after_choosing_successor(tmp_path):
    with _client(tmp_path) as client:
        owner = {'email': 'owner-transfer@example.com', 'password': 'ownerpassword'}
        guest = {'email': 'successor@example.com', 'password': 'memberpassword'}
        client.post('/api/auth/signup', json=owner)
        home = client.get('/api/auth/me').json()['household_id']
        token = client.post('/api/household/invites').json()['token']
        client.post('/api/auth/logout')
        client.post('/api/household/accept-invite', json={**guest, 'token': token})
        successor_id = client.get('/api/auth/me').json()['user_id']
        client.post('/api/auth/logout')
        client.post('/api/auth/login', json=owner)
        assert client.put(f'/api/household/members/{successor_id}/role', json={'role': 'owner'}).status_code == 200
        assert client.post('/api/auth/delete-account', json={'password': owner['password']}).json()['household_deleted'] is False
        assert client.post('/api/auth/login', json=guest).status_code == 200
        assert client.get('/api/auth/me').json()['household_id'] == home
        assert client.get('/api/household/members').json()['members'][0]['household_role'] == 'owner'


def test_forgot_password_says_when_email_is_down(tmp_path, monkeypatch):
    for key in ("RESEND_API_KEY", "MAIL_FROM", "PUBLIC_URL"):
        monkeypatch.delenv(key, raising=False)
    with _client(tmp_path) as client:
        client.post("/api/auth/signup", json={"email": "you@example.com", "password": "correct horse battery staple",
                                              "household_name": "Our house"})
        # Same answer with or without an account, so it doesn't reveal who has one.
        for email in ("you@example.com", "nobody@example.com"):
            res = client.post("/api/auth/forgot-password", json={"email": email})
            assert res.status_code == 503
            assert res.json()["detail"] == "mail_unavailable"
            assert "can't send email" in res.json()["message"]


def test_forgot_password_reports_a_failed_send(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("MAIL_FROM", "Dinnerdesk <hello@example.com>")
    monkeypatch.setenv("PUBLIC_URL", "https://example.com")

    def broken(*_args):
        raise RuntimeError("Resend said no")

    monkeypatch.setattr("app.auth_routes.send_reset_email", broken)
    with _client(tmp_path) as client:
        client.post("/api/auth/signup", json={"email": "you@example.com", "password": "correct horse battery staple",
                                              "household_name": "Our house"})
        assert client.post("/api/auth/forgot-password", json={"email": "you@example.com"}).status_code == 503
        assert client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"}).status_code == 200


def test_username_account_signs_up_and_logs_in_without_email(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("MAIL_FROM", "Dinnerdesk <hello@example.com>")
    monkeypatch.setenv("PUBLIC_URL", "https://example.com")
    with _client(tmp_path) as client:
        res = client.post("/api/auth/signup", json={
            "email": " Kitchen.Fan ", "password": "correct horse battery staple", "household_name": "Ours"})
        assert res.status_code == 200
        me = client.get("/api/auth/me").json()
        assert me["email"] == "kitchen.fan"
        assert me["has_email"] is False
        client.post("/api/auth/logout")
        ok = client.post("/api/auth/login", json={"email": "KITCHEN.FAN", "password": "correct horse battery staple"})
        assert ok.status_code == 200
        # Without a recovery email, a username account can't invite people into its household.
        invite = client.post("/api/household/invites")
        assert invite.status_code == 400
        assert invite.json()["detail"] == "email_required_to_invite"

        taken = client.post("/api/auth/signup", json={
            "email": "kitchen.fan", "password": "correct horse battery staple", "household_name": "x"})
        assert taken.json()["detail"] == "email_taken"
        for bad in ("ab", "has space", "x" * 31):
            res = client.post("/api/auth/signup", json={
                "email": bad, "password": "correct horse battery staple", "household_name": "x"})
            assert res.json()["detail"] == "invalid_username", bad

        # No email means no reset: say so plainly, and never try to send.
        reset = client.post("/api/auth/forgot-password", json={"email": "kitchen.fan"})
        assert reset.status_code == 400
        assert reset.json()["detail"] == "no_email"


def test_unverified_signup_can_confirm_change_and_remove_email(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("MAIL_FROM", "Dinnerdesk <hello@example.com>")
    monkeypatch.setenv("PUBLIC_URL", "https://example.com")
    sent = []
    monkeypatch.setattr("app.auth_routes.send_verify_email", lambda to, link: sent.append((to, link)))
    password = "correct horse battery staple"
    with _client(tmp_path) as client:
        client.post("/api/auth/signup", json={"email": "you@exmaple.com", "password": password, "household_name": "Ours"})
        me = client.get("/api/auth/me").json()
        assert me["email_verified"] is False

        # A new address needs the password, and nothing changes until its link is opened.
        assert client.post("/api/auth/verify-email", json={"email": "you@example.com"}).json()["detail"] == "wrong_password"
        assert client.post("/api/auth/verify-email", json={"email": "you@example.com", "password": password}).status_code == 200
        assert sent[-1][0] == "you@example.com"
        assert client.get("/api/auth/me").json()["email"] == "you@exmaple.com"

        token = sent[-1][1].rsplit("/", 1)[1]
        assert client.post("/api/auth/confirm-email", json={"token": token}).json()["email"] == "you@example.com"
        me = client.get("/api/auth/me").json()
        assert me["email"] == "you@example.com" and me["email_verified"] is True
        assert client.post("/api/auth/confirm-email", json={"token": token}).json()["detail"] == "verify_invalid"
        client.post("/api/auth/logout")
        assert client.post("/api/auth/login", json={"email": "you@example.com", "password": password}).status_code == 200

        # Re-sending to the current address needs no password.
        assert client.post("/api/auth/verify-email", json={}).json()["email"] == "you@example.com"

        # Removing the email: sign in with a username instead. Open links stop working.
        open_token = sent[-1][1].rsplit("/", 1)[1]
        assert client.post("/api/auth/use-username", json={"username": "cook", "password": "nope"}).json()["detail"] == "wrong_password"
        assert client.post("/api/auth/use-username", json={"username": "cook", "password": password}).status_code == 200
        me = client.get("/api/auth/me").json()
        assert me["email"] == "cook" and me["has_email"] is False and me["email_verified"] is False
        assert client.post("/api/auth/confirm-email", json={"token": open_token}).json()["detail"] == "verify_invalid"


def test_confirm_email_refuses_an_address_taken_meanwhile(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("MAIL_FROM", "Dinnerdesk <hello@example.com>")
    monkeypatch.setenv("PUBLIC_URL", "https://example.com")
    sent = []
    monkeypatch.setattr("app.auth_routes.send_verify_email", lambda to, link: sent.append(link))
    password = "correct horse battery staple"
    with _client(tmp_path) as client:
        client.post("/api/auth/signup", json={"email": "a@example.com", "password": password, "household_name": "A"})
        client.post("/api/auth/verify-email", json={"email": "b@example.com", "password": password})
        client.post("/api/auth/logout")
        client.post("/api/auth/signup", json={"email": "b@example.com", "password": password, "household_name": "B"})
        res = client.post("/api/auth/confirm-email", json={"token": sent[-1].rsplit("/", 1)[1]})
        assert res.json()["detail"] == "email_taken"


def test_username_account_adds_a_recovery_email(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("MAIL_FROM", "Dinnerdesk <hello@example.com>")
    monkeypatch.setenv("PUBLIC_URL", "https://example.com")
    sent, links = [], []
    monkeypatch.setattr("app.auth_routes.send_reset_email", lambda to, link: sent.append(to) or True)
    monkeypatch.setattr("app.auth_routes.send_verify_email", lambda to, link: links.append(link.rsplit("/", 1)[1]))
    password = "correct horse battery staple"
    with _client(tmp_path) as client:
        client.post("/api/auth/signup", json={"email": "other@example.com", "password": password, "household_name": "x"})
        client.post("/api/auth/logout")
        client.post("/api/auth/signup", json={"email": "kitchen.fan", "password": password, "household_name": "Ours"})
        add = lambda email, pw=password: client.post("/api/auth/verify-email", json={"email": email, "password": pw})
        assert add("fan@example.com", "nope").json()["detail"] == "wrong_password"
        assert add("nope").json()["detail"] == "invalid_email"
        assert add("other@example.com").json()["detail"] == "email_taken"

        # A typo changes nothing; only the opened link sets the recovery email.
        assert add("fan@exmaple.com").status_code == 200
        assert add(" Fan@Example.com ").status_code == 200
        assert client.get("/api/auth/me").json()["recovery_email"] is None
        assert client.post("/api/auth/confirm-email", json={"token": links[-1]}).status_code == 200
        me = client.get("/api/auth/me").json()
        assert me["email"] == "kitchen.fan" and me["recovery_email"] == "fan@example.com" and me["email_verified"]
        assert client.post("/api/auth/confirm-email", json={"token": links[0]}).json()["detail"] == "verify_invalid"
        assert client.post("/api/household/invites").status_code == 200

        # Either name signs in; resets go to the recovery email.
        client.post("/api/auth/logout")
        assert client.post("/api/auth/login", json={"email": "fan@example.com", "password": password}).status_code == 200
        client.post("/api/auth/logout")
        assert client.post("/api/auth/login", json={"email": "kitchen.fan", "password": password}).status_code == 200
        assert client.post("/api/auth/forgot-password", json={"email": "kitchen.fan"}).status_code == 200
        assert client.post("/api/auth/forgot-password", json={"email": "fan@example.com"}).status_code == 200
        assert sent == ["fan@example.com", "fan@example.com"]

        # Nobody else can take it as a login, recovery email, or by changing their own email.
        client.post("/api/auth/logout")
        taken = client.post("/api/auth/signup", json={"email": "fan@example.com", "password": password, "household_name": "x"})
        assert taken.json()["detail"] == "email_taken"
        assert client.post("/api/auth/login", json={"email": "other@example.com", "password": password}).status_code == 200
        assert add("fan@example.com").json()["detail"] == "email_taken"
        assert client.post("/api/auth/use-username", json={"username": "kitchen.fan", "password": password}).json()["detail"] == "email_taken"

        # Removing it needs the password; then there's no reset address again.
        client.post("/api/auth/logout")
        client.post("/api/auth/login", json={"email": "kitchen.fan", "password": password})
        assert client.post("/api/auth/remove-recovery-email", json={"password": "nope"}).json()["detail"] == "wrong_password"
        assert client.post("/api/auth/remove-recovery-email", json={"password": password}).status_code == 200
        me = client.get("/api/auth/me").json()
        assert me["recovery_email"] is None and me["email_verified"] is False
        assert client.post("/api/auth/forgot-password", json={"email": "kitchen.fan"}).json()["detail"] == "no_email"


def test_tastelab_saves_only_to_own_history(tmp_path):
    vote = lambda rid: {"id": "shared-session", "anon_id": "guest-1", "kind": "snapshot",
                        "body": {"swipes": [{"recipe_id": rid, "liked": True}]}}
    with _client(tmp_path) as victim, TestClient(create_app()) as attacker:
        victim.get("/api/auth/status")
        attacker.get("/api/auth/status")
        assert victim.post("/api/sessions", json=vote("1")).status_code == 200
        assert attacker.post("/api/sessions", json=vote("2")).status_code == 200
        assert victim.get("/api/taste").json()["votes"] == [{"recipe_id": "1", "liked": True}]
        assert attacker.get("/api/taste").json()["votes"] == [{"recipe_id": "2", "liked": True}]
