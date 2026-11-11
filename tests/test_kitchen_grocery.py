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
    monkeypatch.setattr(routes, "_suggest_meals", lambda db, household_id, want, kept=None, plan_id=None: (
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


def test_resending_auto_check_does_not_retick_pantry_items(tmp_path):
    """#172: the web tour saved every pref back, including pantry_auto_check, which re-ticked
    pantry items the user had unchecked. Only a real change to the switch touches the list."""
    with _client(tmp_path) as client:
        pid = _plan_with_soup(client, tmp_path)
        client.post("/api/pantry/items", json={"name": "onion", "have": True})
        client.put("/api/household", json={"prefs": {"pantry_auto_check": True}})
        line = _onion(client, pid)
        assert line["checked"] is True
        client.patch(f"/api/grocery/lines/{line['id']}", json={"checked": False})
        prefs = client.get("/api/household").json()["prefs"]
        client.put("/api/household", json={"prefs": {**prefs, "tour_done": True, "tour_version": 9}})
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


def test_ingredient_aliases_share_pantry_grocery_and_placement(tmp_path):
    with _client(tmp_path) as client:
        pid = client.get("/api/plans/current").json()["id"]
        pantry = client.post("/api/pantry/items", json={"name": "  GREEN   ONIONS ", "have": True})
        assert pantry.status_code == 200
        assert pantry.json()["name"] == "green onions (scallions)"
        assert client.put("/api/grocery/places", json={"name": "Green Onion", "aisle": "other", "store": "mine"}).status_code == 200
        line = client.post(f"/api/plans/{pid}/grocery/lines", json={"name": "green onion", "quantity": "1"})
        assert line.status_code == 200
        assert line.json()["name"] == pantry.json()["name"]
        places = client.get("/api/grocery/places").json()["items"]
        assert len([p for p in places if "green onion" in p["name"]]) == 1


def test_custom_items_and_renames_do_not_change_another_household(tmp_path):
    from fastapi.testclient import TestClient
    from app.db.database import connect
    with _client(tmp_path) as client:
        pid = client.get("/api/plans/current").json()["id"]
        client.post("/api/pantry/items", json={"name": "  FAMILY   SECRET MIX ", "have": True})
        line = client.post(f"/api/plans/{pid}/grocery/lines", json={"name": "green onion"}).json()
        assert client.patch(f"/api/grocery/lines/{line['id']}", json={"custom_text": " FAMILY SECRET MIX ", "aisle": "other"}).status_code == 200
        names = [r["name"] for r in client.get("/api/pantry").json()["items"]]
        assert "family secret mix" in names
        with TestClient(client.app, cookies={"dd_guest": "another-household"}) as other:
            assert "family secret mix" not in [r["name"] for r in other.get("/api/pantry/catalog").json()["items"]]
            assert "family secret mix" not in [r["name"] for r in other.get("/api/grocery-items", params={"q": "family secret"}).json()["items"]]
            assert "family secret mix" not in [r["name"] for r in other.get("/api/grocery/places").json()["items"]]
        db = connect()
        assert db.execute("SELECT canonical_name FROM ingredients WHERE canonical_name = 'green onions (scallions)'").fetchone()
        db.close()


def test_legacy_aisle_alias_survives_refresh_and_rebuild(tmp_path):
    from app.db.database import connect, refresh_aisles
    with _client(tmp_path) as client:
        pid = _plan_with_soup(client, tmp_path)
        db = connect()
        household = db.execute("SELECT household_id FROM plans WHERE id = ?", (pid,)).fetchone()["household_id"]
        db.execute("INSERT INTO grocery_places (household_id, name, store, aisle) VALUES (?, '  ONION  ', 'mine', 'other')", (household,))
        db.commit()
        refresh_aisles(db)
        db.commit()
        assert client.post(f"/api/plans/{pid}/grocery").status_code == 200
        line = _onion(client, pid)
        assert (line["store"], line["aisle"]) == ("mine", "other"), (line, client.get("/api/grocery/places").json())
        db.close()


def test_local_ingredient_rename_survives_rebuild(tmp_path):
    with _client(tmp_path) as client:
        pid = _plan_with_soup(client, tmp_path)
        line = _onion(client, pid)
        assert client.patch(f"/api/grocery/lines/{line['id']}", json={"custom_text": " MY   ONION MIX "}).status_code == 200
        assert client.post(f"/api/plans/{pid}/grocery").status_code == 200
        lines = client.get(f"/api/plans/{pid}/grocery").json()["lines"]
        assert any(r["id"] == line["id"] and r["name"] == "my onion mix" for r in lines)


def test_cleanup_preserves_references_households_and_is_repeatable(tmp_path):
    import json
    from app.db.database import connect
    from app.db.ingredient_cleanup import snapshot, plan_cleanup, apply_cleanup
    with _client(tmp_path) as client:
        pid = _plan_with_soup(client, tmp_path)
        db = connect()
        household = db.execute("SELECT household_id FROM plans WHERE id = ?", (pid,)).fetchone()["household_id"]
        old = db.execute("INSERT INTO ingredients (canonical_name) VALUES ('  GREEN ONION  ')").lastrowid
        keep = db.execute("INSERT INTO ingredients (canonical_name) VALUES ('green onions (scallions)')").lastrowid
        db.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity) VALUES (1, ?, '3')", (old,))
        for hh in (household, 2):
            db.execute("INSERT INTO grocery_places (household_id, name, store, aisle) VALUES (?, '  GREEN ONION  ', ?, 'other')", (hh, str(hh)))
        db.execute("INSERT INTO pantry_items (household_id, ingredient_id, name, quantity) VALUES (?, ?, '  GREEN ONION  ', 'two bags')", (household, old))
        db.execute("INSERT INTO grocery_lines (plan_id, ingredient_id, custom_text, quantity) VALUES (?, ?, ' GREEN ONION ', '1 bag')", (pid, old))
        db.execute("INSERT INTO ingredient_reports (household_id, ingredient_id, item_name, reason, snapshot_json, created_at) VALUES (?, ?, 'GREEN ONION', 'name', '{}', '2026-11-03')", (household, old))
        db.commit()
        before = snapshot(db)
        assert plan_cleanup(before)["duplicate_ingredients"] >= 1
        backup = tmp_path / "ingredient-backup.json"
        apply_cleanup(db, backup)
        assert json.loads(backup.read_text(encoding="utf-8")) == before
        assert db.execute("SELECT ingredient_id FROM recipe_ingredients WHERE quantity = '3'").fetchone()["ingredient_id"] == keep
        grocery = db.execute("SELECT ingredient_id, custom_text, quantity FROM grocery_lines WHERE quantity = '1 bag'").fetchone()
        assert grocery["ingredient_id"] == keep and grocery["custom_text"] == "green onions (scallions)"
        report = db.execute("SELECT ingredient_id, item_name, snapshot_json FROM ingredient_reports").fetchone()
        assert report["ingredient_id"] == keep and report["item_name"] == "GREEN ONION" and report["snapshot_json"] == "{}"
        pantry = db.execute("SELECT * FROM pantry_items WHERE quantity = 'two bags'").fetchone()
        assert pantry["name"] == "green onions (scallions)" and pantry["ingredient_id"] == keep
        for hh in (household, 2):
            place = db.execute("SELECT * FROM grocery_places WHERE household_id = ?", (hh,)).fetchone()
            assert place["store"] == str(hh)
        after = snapshot(db)
        assert plan_cleanup(after)["duplicate_ingredients"] == 0
        apply_cleanup(db, tmp_path / "second-backup.json")
        assert snapshot(db) == after
        db.close()


def test_cleanup_refuses_conflicting_household_placements(tmp_path):
    import pytest
    from app.db.database import connect
    from app.db.ingredient_cleanup import snapshot, apply_cleanup
    with _client(tmp_path):
        db = connect()
        for name, aisle in (("green onion", "produce"), ("green onions (scallions)", "other")):
            db.execute("INSERT INTO grocery_places (household_id, name, store, aisle) VALUES (2, ?, '', ?)", (name, aisle))
        db.commit()
        before = snapshot(db)
        with pytest.raises(ValueError, match="Resolve preview conflicts"):
            apply_cleanup(db, tmp_path / "not-written.json")
        assert snapshot(db) == before
        assert not (tmp_path / "not-written.json").exists()
        db.close()


def test_cleanup_requires_unused_backup_and_refuses_metadata_conflicts(tmp_path):
    import pytest
    from app.db.database import connect
    from app.db.ingredient_cleanup import snapshot, apply_cleanup
    with _client(tmp_path):
        db = connect()
        backup = tmp_path / "existing-backup.json"
        backup.write_text("keep original", encoding="utf-8")
        before = snapshot(db)
        with pytest.raises(FileExistsError):
            apply_cleanup(db, backup)
        assert snapshot(db) == before
        assert backup.read_text(encoding="utf-8") == "keep original"
        db.execute("INSERT INTO ingredients (canonical_name, package_size) VALUES ('green onion', '2')")
        db.execute("INSERT INTO ingredients (canonical_name, package_size) VALUES ('green onions (scallions)', '4')")
        db.commit()
        before = snapshot(db)
        with pytest.raises(ValueError, match="Resolve preview conflicts"):
            apply_cleanup(db, tmp_path / "not-written.json")
        assert snapshot(db) == before
        db.close()
