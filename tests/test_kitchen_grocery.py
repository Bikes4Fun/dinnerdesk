"""Kitchen settings (pantry, staples, store/aisle) show up on the grocery list."""

from tests.test_api import _client, _link_soup_onion


def test_family_portions_default_new_meals_without_rescaling_existing_plan(tmp_path):
    with _client(tmp_path) as client:
        pid = _plan_with_soup(client, tmp_path)
        before = client.get("/api/plans/current").json()
        assert client.put("/api/household", json={"prefs": {"family_portions": 8}}).status_code == 200
        assert client.get("/api/plans/current").json()["slots"] == before["slots"]
        added = client.put(f"/api/plans/{pid}/slots", json={"slots": [{"recipe_id": 1}]}).json()
        assert added["slots"][0]["servings"] == 8
        assert _onion(client, pid)["quantity"] == "2"
        assert client.get("/api/recipes/1").json()["servings"] == 4
        chosen = client.put(f"/api/plans/{pid}/slots", json={"slots": [{"recipe_id": 1, "servings": 3}]}).json()
        assert chosen["slots"][0]["servings"] == 3


def test_family_portions_default_suggested_meals(tmp_path, monkeypatch):
    import app.routes as routes
    monkeypatch.setattr(routes, "_suggest_meals", lambda db, household_id, want: (
        [{"id": 1, "reasons": []}], "Suggested dinners", {"1": []}))
    with _client(tmp_path) as client:
        client.put("/api/household", json={"prefs": {"family_portions": 8}})
        response = client.post("/api/plans", json={"meal_count": 1})
        assert response.status_code == 200
        assert response.json()["slots"][0]["servings"] == 8


def test_unset_or_invalid_family_portions_use_recipe_servings(tmp_path):
    with _client(tmp_path) as client:
        pid = client.get("/api/plans/current").json()["id"]
        for portions in [None, 0, 51, True, "8"]:
            client.put("/api/household", json={"prefs": {"family_portions": portions}})
            added = client.put(f"/api/plans/{pid}/slots", json={"slots": [{"recipe_id": 1}]}).json()
            assert added["slots"][0]["servings"] == 4


def _onion(client, pid):
    lines = client.get(f"/api/plans/{pid}/grocery").json()["lines"]
    return next(x for x in lines if "onion" in x["name"])


def _plan_with_soup(client, tmp_path):
    _link_soup_onion(tmp_path)
    pid = client.get("/api/plans/current").json()["id"]
    client.put(
        f"/api/plans/{pid}/slots",
        json={"slots": [{"recipe_id": 1, "day_index": 1, "meal_type": "dinner", "servings": 4}]},
    )
    return pid


def test_pantry_item_is_checked_when_auto_check_is_on(tmp_path):
    with _client(tmp_path) as client:
        pid = _plan_with_soup(client, tmp_path)
        client.put("/api/household", json={"prefs": {"pantry_auto_check": True}})
        assert _onion(client, pid)["checked"] is False
        added = client.post("/api/pantry/items", json={"name": "onion", "have": True})
        assert _onion(client, pid)["checked"] is True
        client.patch(f"/api/pantry/items/{added.json()['id']}", json={"have": False})
        assert _onion(client, pid)["checked"] is False


def test_pantry_item_stays_unchecked_when_auto_check_is_off(tmp_path):
    with _client(tmp_path) as client:
        pid = _plan_with_soup(client, tmp_path)
        client.post("/api/pantry/items", json={"name": "onion", "have": True})
        assert _onion(client, pid)["checked"] is False
        client.put("/api/household", json={"prefs": {"pantry_auto_check": True}})
        assert _onion(client, pid)["checked"] is True
        client.put("/api/household", json={"prefs": {"pantry_auto_check": False}})
        assert _onion(client, pid)["checked"] is False


def test_staple_checks_and_unchecks(tmp_path):
    with _client(tmp_path) as client:
        pid = _plan_with_soup(client, tmp_path)
        added = client.post("/api/pantry/items", json={"name": "onion", "have": True, "never_shop": True})
        assert _onion(client, pid)["checked"] is True
        client.patch(f"/api/pantry/items/{added.json()['id']}", json={"never_shop": False, "have": False})
        assert _onion(client, pid)["checked"] is False


def test_store_and_aisle_survive_a_rebuild(tmp_path):
    with _client(tmp_path) as client:
        pid = _plan_with_soup(client, tmp_path)
        line = _onion(client, pid)
        client.patch(f"/api/grocery/lines/{line['id']}", json={"store": "costco", "aisle": "pantry"})
        client.post(f"/api/plans/{pid}/grocery")
        again = _onion(client, pid)
        assert again["store"] == "costco"
        assert again["aisle"] == "pantry"
