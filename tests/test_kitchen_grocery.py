"""Kitchen settings (pantry, staples, store/aisle) show up on the grocery list."""

from tests.test_api import _client, _link_soup_onion


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
