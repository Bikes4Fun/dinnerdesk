import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.database import connect, init_db, now
from app.main import create_app


def _seed(path: Path) -> None:
    db = connect()
    init_db(db)
    ts = now()
    db.execute(
        "INSERT INTO households (id, name, prefs_json, created_at) VALUES (2, 'Other', '{}', ?)",
        (ts,),
    )
    db.execute(
        """INSERT INTO recipes (
            household_id, slug, name, servings, cooking_minutes,
            instructions_json, cookware_json, source_url, provenance_json,
            photo_path, created_at, updated_at
        ) VALUES (NULL, 'soup', 'Soup', 4, 20, '[]', '[]', '',
            '{"instructions_copied_from_third_party": false}', 'food/soup.jpg', ?, ?)""",
        (ts, ts),
    )
    db.execute(
        """INSERT INTO recipes (
            household_id, slug, name, servings, cooking_minutes,
            instructions_json, cookware_json, source_url, provenance_json,
            photo_path, created_at, updated_at
        ) VALUES (2, 'secret', 'Secret stew', 2, 10, '[]', '[]', '', '{}', '', ?, ?)""",
        (ts, ts),
    )
    db.execute(
        "INSERT INTO ingredients (canonical_name, aliases_json, aisle) VALUES ('onion', '[]', 'produce')"
    )
    db.execute(
        "INSERT INTO pantry_items (household_id, ingredient_id, name, have, never_shop, zone) VALUES (2, 1, 'hidden salt', 1, 0, 'dry')"
    )
    db.execute(
        "INSERT INTO plans (household_id, start_date, days, title, created_at) VALUES (2, date('now'), 7, 'Theirs', ?)",
        (ts,),
    )
    db.execute(
        """INSERT INTO grocery_lines (
            plan_id, ingredient_id, quantity, aisle, checked, from_pantry,
            never_shop, custom_text, source_slots_json
        ) VALUES (1, 1, '1', 'produce', 0, 0, 0, 'hidden line', '[]')"""
    )
    db.commit()
    db.close()


def _client(tmp_path: Path) -> TestClient:
    _seed(tmp_path)
    app = create_app()
    return TestClient(app)


def test_household_cannot_see_other_household_pantry(tmp_path):
    with _client(tmp_path) as client:
        res = client.get("/api/pantry")
        assert res.status_code == 200
        names = [i["name"] for i in res.json()["items"]]
        assert "hidden salt" not in names


def test_household_cannot_see_other_household_recipe(tmp_path):
    with _client(tmp_path) as client:
        listed = client.get("/api/recipes")
        names = [r["name"] for r in listed.json()["recipes"]]
        assert "Soup" in names
        assert "Secret stew" not in names
        assert client.get("/api/recipes/2").status_code == 404


def test_cannot_patch_other_household_grocery(tmp_path):
    with _client(tmp_path) as client:
        res = client.patch("/api/grocery/lines/1", json={"checked": True})
        assert res.status_code == 404


def test_catalog_is_read_only_copy_on_write(tmp_path):
    with _client(tmp_path) as client:
        denied = client.delete("/api/recipes/1")
        assert denied.status_code == 403
        patched = client.patch("/api/recipes/1", json={"as_copy": True, "name": "Our soup"})
        assert patched.status_code == 200
        body = patched.json()
        assert body["id"] != 1
        assert body["catalog"] is False
        assert body["parent_recipe_id"] == 1
        assert body["name"] == "Our soup"
        original = client.get("/api/recipes/1").json()
        assert original["name"] == "Soup"
        assert original["catalog"] is True


def test_catalog_in_place_edit(tmp_path):
    with _client(tmp_path) as client:
        patched = client.patch(
            "/api/recipes/1",
            json={
                "name": "Soup (fixed)",
                "ingredients": [{"name": "onion", "quantity": "1"}],
                "instructions": [{"text": "Chop onion", "prep": True, "ings": ""}],
            },
        )
        assert patched.status_code == 200
        body = patched.json()
        assert body["id"] == 1
        assert body["catalog"] is True
        assert body["name"] == "Soup (fixed)"
        assert body["ingredients"][0]["name"] == "yellow onion"
        assert body["instructions"][0]["prep"] is True
        assert body["instructions"][0]["ings"] == ""
        db = connect()
        catalog = db.execute("SELECT name FROM recipes WHERE id = 1").fetchone()
        db.close()
        assert catalog["name"] == "Soup"
        shown = client.get("/api/recipes/1").json()
        assert shown["name"] == "Soup (fixed)"
        assert shown["edited"] is True


def test_restore_overlay_keeps_favorite_and_id(tmp_path):
    with _client(tmp_path) as client:
        client.put("/api/recipes/1/favorite", json={"on": True})
        client.put("/api/recipes/1/hidden", json={"on": True})
        client.patch("/api/recipes/1", json={"name": "Kitchen soup"})
        restored = client.delete("/api/recipes/1/edit")
        assert restored.status_code == 200
        body = restored.json()
        assert body["id"] == 1
        assert body["name"] == "Soup"
        assert body["catalog"] is True
        assert body["edited"] is False
        assert body["favorited"] is True
        assert body["hidden"] is True
        assert client.delete("/api/recipes/1/edit").status_code == 404


def test_catalog_publish_updates_original_keeps_overlay(tmp_path):
    from app.db.catalog import upsert_catalog_recipe

    with _client(tmp_path) as client:
        assert client.get("/api/recipes/1").json()["instructions_source"] is None
        client.patch("/api/recipes/1", json={"in_place": True, "name": "Kitchen soup"})
        db = connect()
        result = upsert_catalog_recipe(
            db,
            {
                "slug": "soup",
                "instructions_source": "dinnerdesk",
                "instructions_copied_from_third_party": False,
                "instructions_rewritten_from": "fictional-source",
                "name": "Published soup",
                "servings": 6,
                "cooking_minutes": 30,
                "instructions": [{"text": "Simmer", "prep": False}],
                "ingredients": [{"name": "onion", "quantity": "2"}],
                "photo_path": "food/soup.jpg",
            },
            {},
        )
        db.commit()
        overlays = db.execute(
            "SELECT COUNT(*) AS c FROM household_recipe_edits WHERE recipe_id = 1"
        ).fetchone()["c"]
        catalog = db.execute("SELECT name, photo_path, provenance_json FROM recipes WHERE id = 1").fetchone()
        db.close()
        assert result == "update"
        assert overlays == 1
        assert catalog["name"] == "Published soup"
        assert catalog["photo_path"] == "food/soup.jpg"
        provenance = json.loads(catalog["provenance_json"])
        assert "instructions_customized" not in provenance
        assert provenance["instructions_rewritten_from"] == "fictional-source"
        shown = client.get("/api/recipes/1").json()
        assert shown["instructions_source"] == "dinnerdesk"
        assert shown["instructions_copied_from_third_party"] is False
        assert "instructions_customized" not in shown
        assert shown["id"] == 1
        assert shown["name"] == "Kitchen soup"
        assert shown["edited"] is True
        restored = client.delete("/api/recipes/1/edit").json()
        assert restored["name"] == "Published soup"
        assert restored["edited"] is False
        assert restored["servings"] == 6


def test_copy_does_not_share_overlay(tmp_path):
    with _client(tmp_path) as client:
        copied = client.patch("/api/recipes/1", json={"as_copy": True, "name": "Our soup"})
        cid = copied.json()["id"]
        assert cid != 1
        client.patch(f"/api/recipes/{cid}", json={"name": "Our soup v2"})
        original = client.get("/api/recipes/1").json()
        assert original["name"] == "Soup"
        assert original["catalog"] is True
        ours = client.get(f"/api/recipes/{cid}").json()
        assert ours["name"] == "Our soup v2"
        assert ours["catalog"] is False
        db = connect()
        overlays = db.execute("SELECT recipe_id FROM household_recipe_edits").fetchall()
        kitchen = db.execute("SELECT name, household_id FROM recipes WHERE id = ?", (cid,)).fetchone()
        catalog = db.execute("SELECT name FROM recipes WHERE id = 1").fetchone()
        db.close()
        assert [r["recipe_id"] for r in overlays] == []
        assert kitchen["household_id"] is not None
        assert kitchen["name"] == "Our soup v2"
        assert catalog["name"] == "Soup"


def test_kitchen_owned_save_updates_row(tmp_path):
    with _client(tmp_path) as client:
        created = client.post(
            "/api/recipes",
            json={
                "name": "Blank stew",
                "servings": 3,
                "ingredients": [{"name": "onion", "quantity": "1"}],
                "instructions": [{"text": "Simmer", "ings": "1 onion", "prep": False}],
            },
        )
        assert created.status_code == 200
        rid = created.json()["id"]
        assert created.json()["catalog"] is False
        patched = client.patch(
            f"/api/recipes/{rid}",
            json={"name": "Blank stew v2", "instructions": [{"text": "Boil", "ings": "", "prep": True}]},
        )
        assert patched.status_code == 200
        body = patched.json()
        assert body["id"] == rid
        assert body["catalog"] is False
        assert body["name"] == "Blank stew v2"
        assert body["instructions"][0]["ings"] == ""
        assert body["instructions"][0]["prep"] is True
        assert client.delete(f"/api/recipes/{rid}/edit").status_code == 400
        db = connect()
        row = db.execute("SELECT name, household_id FROM recipes WHERE id = ?", (rid,)).fetchone()
        overlays = db.execute(
            "SELECT COUNT(*) AS c FROM household_recipe_edits WHERE recipe_id = ?", (rid,)
        ).fetchone()["c"]
        db.close()
        assert row["name"] == "Blank stew v2"
        assert row["household_id"] is not None
        assert overlays == 0


def test_overlay_changes_grocery_without_new_id(tmp_path):
    with _client(tmp_path) as client:
        _link_soup_onion(tmp_path)
        pid = client.get("/api/plans/current").json()["id"]
        client.put(
            f"/api/plans/{pid}/slots",
            json={"slots": [{"recipe_id": 1, "day_index": 1, "meal_type": "dinner", "servings": 4}]},
        )
        before = client.get(f"/api/plans/{pid}/grocery").json()["lines"]
        assert any("onion" in x["name"] for x in before)
        patched = client.patch(
            "/api/recipes/1",
            json={"ingredients": [{"name": "lime", "quantity": "2"}]},
        )
        assert patched.json()["id"] == 1
        groc = client.get(f"/api/plans/{pid}/grocery").json()["lines"]
        names = [x["name"] for x in groc]
        assert any("lime" in n for n in names)
        assert not any("onion" in n for n in names)
        # catalog onion still on the catalog row
        db = connect()
        catalog_name = db.execute("SELECT name FROM recipes WHERE id = 1").fetchone()["name"]
        catalog_ing = db.execute(
            """SELECT i.canonical_name FROM recipe_ingredients ri
               JOIN ingredients i ON i.id = ri.ingredient_id
               WHERE ri.recipe_id = 1"""
        ).fetchone()["canonical_name"]
        db.close()
        assert catalog_name == "Soup"
        assert "onion" in catalog_ing


def test_copy_leaves_plan_on_original(tmp_path):
    with _client(tmp_path) as client:
        pid = client.get("/api/plans/current").json()["id"]
        client.put(
            f"/api/plans/{pid}/slots",
            json={"slots": [{"recipe_id": 1, "day_index": 1, "meal_type": "dinner", "servings": 4}]},
        )
        copied = client.patch("/api/recipes/1", json={"as_copy": True, "name": "Our soup"})
        cid = copied.json()["id"]
        slots = client.get("/api/plans/current").json()["slots"]
        assert [s["recipe_id"] for s in slots] == [1]
        assert cid != 1


def test_copy_after_overlay_is_independent(tmp_path):
    with _client(tmp_path) as client:
        client.patch("/api/recipes/1", json={"name": "Kitchen soup"})
        copied = client.patch("/api/recipes/1", json={"as_copy": True, "name": "Our soup"})
        cid = copied.json()["id"]
        client.patch(f"/api/recipes/{cid}", json={"name": "Our soup v2"})
        original = client.get("/api/recipes/1").json()
        assert original["id"] == 1
        assert original["name"] == "Kitchen soup"
        assert original["catalog"] is True
        ours = client.get(f"/api/recipes/{cid}").json()
        assert ours["name"] == "Our soup v2"
        db = connect()
        catalog = db.execute("SELECT name FROM recipes WHERE id = 1").fetchone()["name"]
        db.close()
        assert catalog == "Soup"


def test_taste_catalog_uses_database_not_json_copy(tmp_path, monkeypatch):
    from app.domain import recipe_photos

    monkeypatch.setattr(recipe_photos, "USE", {"soup.jpg"})
    with _client(tmp_path) as client:
        db = connect()
        db.execute("UPDATE recipes SET photo_path = 'food/soup.jpg' WHERE id = 1")
        db.execute(
            """INSERT INTO recipe_ingredients
               (recipe_id, ingredient_id, quantity, unit, note, sort)
               VALUES (1, 1, '1', '', '', 0)"""
        )
        db.commit()
        db.close()
        res = client.get("/api/catalog")
        assert res.status_code == 200
        names = [r["name"] for r in res.json()["recipes"]]
        assert "Soup" in names
        assert "Secret stew" not in names
        soup = next(r for r in res.json()["recipes"] if r["name"] == "Soup")
        assert soup["recipe_id"] == 1
        assert soup["photo"] == "/food/soup.jpg"
        assert "onion" in soup["ingredients"]


def test_templates_list_families(tmp_path):
    with _client(tmp_path) as client:
        res = client.get("/api/templates")
        assert res.status_code == 200
        ids = [f["id"] for f in res.json()["families"]]
        assert "burrito_bowls" in ids
        assert "burgers" in ids


def test_get_recipe_does_not_copy(tmp_path):
    with _client(tmp_path) as client:
        db = connect()
        before = db.execute("SELECT COUNT(*) AS c FROM recipes").fetchone()["c"]
        db.close()
        assert client.get("/api/recipes/1").status_code == 200
        db = connect()
        after = db.execute("SELECT COUNT(*) AS c FROM recipes").fetchone()["c"]
        db.close()
        assert after == before


def test_in_place_keeps_step_newlines(tmp_path):
    text = "Mix:\n- garlic\n- lemon"
    with _client(tmp_path) as client:
        patched = client.patch(
            "/api/recipes/1",
            json={"in_place": True, "instructions": [{"text": text, "prep": False}]},
        )
        assert patched.status_code == 200
        assert patched.json()["instructions"][0]["text"] == text
        assert client.get("/api/recipes/1").json()["instructions"][0]["text"] == text


def test_can_mark_slot_cooked(tmp_path):
    with _client(tmp_path) as client:
        plan = client.get("/api/plans/current").json()
        saved = client.put(
            f"/api/plans/{plan['id']}/slots",
            json={"slots": [{"recipe_id": 1, "day_index": None, "meal_type": "dinner", "servings": 4}]},
        )
        slot = saved.json()["slots"][0]
        assert slot["cooked"] is False
        patched = client.patch(f"/api/slots/{slot['id']}", json={"cooked": True})
        assert patched.status_code == 200
        assert patched.json()["cooked"] is True
        moved = client.put(
            f"/api/plans/{plan['id']}/slots",
            json={"slots": [{"recipe_id": 1, "day_index": 2, "meal_type": "dinner", "servings": 4}]},
        )
        assert moved.json()["slots"][0]["cooked"] is True
        assert moved.json()["slots"][0]["day_index"] == 2


def test_cannot_patch_other_household_slot(tmp_path):
    with _client(tmp_path) as client:
        db = connect()
        db.execute(
            """INSERT INTO plan_slots (plan_id, day_index, meal_type, recipe_id, servings, notes, sort, cooked)
               VALUES (1, NULL, 'dinner', 2, 2, '', 0, 0)"""
        )
        db.commit()
        slot_id = db.execute("SELECT id FROM plan_slots WHERE plan_id = 1").fetchone()[0]
        db.close()
        res = client.patch(f"/api/slots/{slot_id}", json={"cooked": True})
        assert res.status_code == 404


def test_try_later_does_not_copy_catalog(tmp_path):
    with _client(tmp_path) as client:
        on = client.put("/api/recipes/1/try", json={"on": True})
        assert on.status_code == 200
        assert on.json()["id"] == 1
        assert on.json()["to_try"] is True
        assert on.json()["catalog"] is True
        listed = client.get("/api/recipes").json()["recipes"]
        soup = next(r for r in listed if r["id"] == 1)
        assert soup["to_try"] is True
        off = client.put("/api/recipes/1/try", json={"on": False})
        assert off.json()["to_try"] is False


def test_favorite_does_not_copy_catalog(tmp_path):
    with _client(tmp_path) as client:
        on = client.put("/api/recipes/1/favorite", json={"on": True})
        assert on.status_code == 200
        assert on.json()["id"] == 1
        assert on.json()["favorited"] is True
        assert on.json()["catalog"] is True
        listed = client.get("/api/recipes").json()["recipes"]
        soup = next(r for r in listed if r["id"] == 1)
        assert soup["favorited"] is True
        off = client.put("/api/recipes/1/favorite", json={"on": False})
        assert off.json()["favorited"] is False


def test_hide_recipe_is_kitchen_only(tmp_path):
    with _client(tmp_path) as client:
        hid = client.put("/api/recipes/1/hidden", json={"on": True})
        assert hid.status_code == 200
        assert hid.json()["id"] == 1
        assert hid.json()["hidden"] is True
        assert hid.json()["catalog"] is True
        listed = client.get("/api/recipes").json()["recipes"]
        assert all(r["id"] != 1 for r in listed)
        still = client.get("/api/recipes/1")
        assert still.status_code == 200
        assert still.json()["name"] == "Soup"
        assert still.json()["catalog"] is True
        plan = client.get("/api/plans/current").json()
        saved = client.put(
            f"/api/plans/{plan['id']}/slots",
            json={"slots": [{"recipe_id": 1, "day_index": 0, "meal_type": "dinner", "servings": 4}]},
        )
        assert saved.status_code == 200
        assert saved.json()["slots"][0]["recipe_id"] == 1
        hidden_list = client.get("/api/recipes?hidden=true").json()["recipes"]
        assert [r["id"] for r in hidden_list] == [1]
        off = client.put("/api/recipes/1/hidden", json={"on": False})
        assert off.json()["hidden"] is False
        names = [r["name"] for r in client.get("/api/recipes").json()["recipes"]]
        assert "Soup" in names


def test_list_shows_kitchen_overlay_name(tmp_path):
    with _client(tmp_path) as client:
        client.patch("/api/recipes/1", json={"in_place": True, "name": "Kitchen soup"})
        listed = client.get("/api/recipes").json()["recipes"]
        soup = next(r for r in listed if r["id"] == 1)
        assert soup["name"] == "Kitchen soup"
        assert soup["catalog"] is True
        found = client.get("/api/recipes?q=Kitchen").json()["recipes"]
        assert any(r["id"] == 1 for r in found)
        missed = client.get("/api/recipes?q=DefinitelyNotSoup").json()["recipes"]
        assert all(r["id"] != 1 for r in missed)


def test_pantry_catalog_and_upsert(tmp_path):
    with _client(tmp_path) as client:
        catalog = client.get("/api/pantry/catalog")
        assert catalog.status_code == 200
        names = [i["name"] for i in catalog.json()["items"]]
        assert "salt" in names
        assert "sweet potatoes" in names
        assert "sweet potato" not in names
        assert "russet potatoes" in names
        assert "yellow potatoes" in names
        assert "red potatoes" in names
        assert "white potatoes" in names
        added = client.post("/api/pantry/items", json={"name": "garlic", "have": True})
        assert added.status_code == 200
        assert added.json()["have"] is True
        mine = client.get("/api/pantry").json()["items"]
        assert any(i["name"] == "garlic" and i["have"] for i in mine)
        off = client.post("/api/pantry/items", json={"name": "garlic", "have": False})
        assert off.json()["have"] is False
        singular = client.post("/api/pantry/items", json={"name": "sweet potato", "have": True})
        assert singular.json()["name"] == "sweet potatoes"
        catalog_names = [i["name"] for i in client.get("/api/pantry/catalog").json()["items"]]
        assert catalog_names.count("sweet potatoes") == 1
        assert "sweet potato" not in catalog_names


def test_overrides_roundtrip(tmp_path):
    with _client(tmp_path) as client:
        empty = client.get("/api/overrides")
        assert empty.status_code == 200
        assert empty.json()["items"] == []
        added = client.post(
            "/api/overrides",
            json={"from_name": "bone-in thighs", "to_name": "boneless thighs"},
        )
        assert added.status_code == 200
        items = added.json()["items"]
        assert len(items) == 1
        assert items[0]["from_name"] == "bone-in thighs"
        gone = client.delete(f"/api/overrides/{items[0]['id']}")
        assert gone.json()["items"] == []


def test_grocery_item_search_uses_catalog(tmp_path):
    with _client(tmp_path) as client:
        res = client.get("/api/grocery-items", params={"q": "cayen"})
        assert res.status_code == 200
        names = [i["name"] for i in res.json()["items"]]
        assert names
        assert names[0] == "cayenne pepper"


def test_grocery_item_search_bread_flour_and_one_ap_flour(tmp_path):
    with _client(tmp_path) as client:
        bread = client.get("/api/grocery-items", params={"q": "bread flour"}).json()
        names = [i["name"] for i in bread["items"]]
        assert names[0] == "bread flour"
        flour = client.get("/api/grocery-items", params={"q": "all purpose flour", "limit": 20}).json()
        ap = [n["name"] for n in flour["items"] if "purpose flour" in n["name"].replace("-", " ")]
        assert ap == ["all-purpose flour"]


def test_grocery_item_search_is_catalog_only(tmp_path):
    with _client(tmp_path) as client:
        db = connect()
        db.execute(
            "INSERT INTO ingredients (canonical_name, aliases_json, aisle) VALUES ('1 cup water', '[]', 'other')"
        )
        db.execute(
            "INSERT INTO ingredients (canonical_name, aliases_json, aisle) VALUES ('usb-c', '[]', 'other')"
        )
        db.commit()
        db.close()
        cup = client.get("/api/grocery-items", params={"q": "cup"}).json()
        names = [i["name"] for i in cup["items"]]
        assert all(not n[0].isdigit() for n in names if n)
        assert "1 cup water" not in names
        usb = client.get("/api/grocery-items", params={"q": "usb"}).json()
        assert "usb-c" not in [i["name"] for i in usb["items"]]
        jals = client.get("/api/grocery-items", params={"q": "jalap", "limit": 20}).json()
        peppers = [i["name"] for i in jals["items"] if "jalape" in i["name"]]
        assert len(peppers) == 1


def test_custom_grocery_line_stays_off_catalog(tmp_path):
    with _client(tmp_path) as client:
        plan_id = client.get("/api/plans/current").json()["id"]
        added = client.post(
            f"/api/plans/{plan_id}/grocery/lines",
            json={"name": "usb-c"},
        )
        assert added.status_code == 200
        assert added.json()["name"] == "usb-c"
        db = connect()
        row = db.execute(
            "SELECT id FROM ingredients WHERE canonical_name = ?", ("usb-c",)
        ).fetchone()
        db.close()
        assert row is None
        hits = client.get("/api/grocery-items", params={"q": "usb"}).json()
        assert "usb-c" not in [i["name"] for i in hits["items"]]
        client.post(f"/api/plans/{plan_id}/grocery")
        names = [x["name"] for x in client.get(f"/api/plans/{plan_id}/grocery").json()["lines"]]
        assert "usb-c" in names


def test_rebuild_keeps_checks_on_same_item(tmp_path):
    with _client(tmp_path) as client:
        _link_soup_onion(tmp_path)
        pid = client.get("/api/plans/current").json()["id"]
        client.put(
            f"/api/plans/{pid}/slots",
            json={"slots": [{"recipe_id": 1, "day_index": 1, "meal_type": "dinner", "servings": 4}]},
        )
        groc = client.get(f"/api/plans/{pid}/grocery").json()["lines"]
        onion = next(x for x in groc if "onion" in x["name"])
        client.patch(f"/api/grocery/lines/{onion['id']}", json={"checked": True})
        rebuilt = client.post(f"/api/plans/{pid}/grocery").json()["lines"]
        still = next(x for x in rebuilt if "onion" in x["name"])
        assert still["checked"] is True
        assert still["quantity"] == onion["quantity"]


def test_dev_notes_do_not_copy_catalog(tmp_path):
    with _client(tmp_path) as client:
        saved = client.put("/api/recipes/1/dev-notes", json={"text": "same salad as 17661"})
        assert saved.status_code == 200
        assert saved.json()["id"] == 1
        assert saved.json()["catalog"] is True
        assert saved.json()["dev_notes"] == "same salad as 17661"
        assert client.get("/api/recipes/1").json()["dev_notes"] == "same salad as 17661"


def _link_soup_onion(tmp_path: Path) -> None:
    db = connect()
    db.execute(
        """INSERT INTO recipe_ingredients
           (recipe_id, ingredient_id, quantity, unit, note, sort)
           VALUES (1, 1, '1', '', '', 0)"""
    )
    db.commit()
    db.close()


def test_add_to_plan_keeps_catalog_recipe(tmp_path):
    with _client(tmp_path) as client:
        client.patch("/api/recipes/1", json={"in_place": True, "name": "Kitchen soup"})
        plan = client.get("/api/plans/current").json()
        saved = client.put(
            f"/api/plans/{plan['id']}/slots",
            json={"slots": [{"recipe_id": 1, "day_index": 1, "meal_type": "dinner", "servings": 4}]},
        )
        assert saved.status_code == 200
        slot = saved.json()["slots"][0]
        assert slot["recipe_id"] == 1
        assert slot["recipe_name"] == "Kitchen soup"
        rec = client.get("/api/recipes/1").json()
        assert rec["catalog"] is True
        assert rec["name"] == "Kitchen soup"
        assert rec["id"] == 1
        db = connect()
        copies = db.execute(
            "SELECT id FROM recipes WHERE household_id IS NOT NULL AND parent_recipe_id = 1"
        ).fetchall()
        catalog = db.execute(
            "SELECT name, household_id FROM recipes WHERE id = 1"
        ).fetchone()
        db.close()
        assert copies == []
        assert catalog["name"] == "Soup"
        assert catalog["household_id"] is None


def test_plan_slot_patch_and_grocery(tmp_path):
    with _client(tmp_path) as client:
        _link_soup_onion(tmp_path)
        plan = client.get("/api/plans/current").json()
        pid = plan["id"]
        saved = client.put(
            f"/api/plans/{pid}/slots",
            json={
                "slots": [
                    {"recipe_id": 1, "day_index": None, "meal_type": "dinner", "servings": 4},
                    {"recipe_id": 1, "day_index": 3, "meal_type": "dinner", "servings": 4},
                ]
            },
        )
        a, b = saved.json()["slots"]
        groc = client.get(f"/api/plans/{pid}/grocery").json()["lines"]
        onion = next(x for x in groc if "onion" in x["name"])
        assert onion["quantity"] == "2"
        assert len([x for x in groc if "onion" in x["name"]]) == 1
        cooked = client.patch(f"/api/slots/{a['id']}", json={"cooked": True})
        assert cooked.json()["cooked"] is True
        after_cook = client.get(f"/api/plans/{pid}/grocery").json()["lines"]
        still = next(x for x in after_cook if "onion" in x["name"])
        assert still["id"] == onion["id"]
        assert still["quantity"] == "2"
        moved = client.patch(f"/api/slots/{a['id']}", json={"day_index": 2})
        assert moved.json()["cooked"] is True
        assert moved.json()["day_index"] == 2
        plan_now = client.get("/api/plans/current").json()
        thu = next(s for s in plan_now["slots"] if s["id"] == b["id"])
        assert thu["day_index"] == 3
        scaled = client.patch(f"/api/slots/{a['id']}", json={"servings": 8})
        assert scaled.json()["servings"] == 8
        after_scale = client.get(f"/api/plans/{pid}/grocery").json()["lines"]
        bigger = next(x for x in after_scale if "onion" in x["name"])
        assert bigger["quantity"] == "3"
        gone = client.delete(f"/api/slots/{a['id']}")
        assert gone.status_code == 200
        assert [s["id"] for s in gone.json()["slots"]] == [b["id"]]
        leftover = client.get(f"/api/plans/{pid}/grocery").json()["lines"]
        one = next(x for x in leftover if "onion" in x["name"])
        assert one["quantity"] == "1"
        parked = client.patch(f"/api/slots/{b['id']}", json={"unschedule": True})
        assert parked.json()["day_index"] is None
        still_shop = client.get(f"/api/plans/{pid}/grocery").json()["lines"]
        assert any("onion" in x["name"] for x in still_shop)
        client.delete(f"/api/slots/{b['id']}")
        empty = client.get(f"/api/plans/{pid}/grocery").json()["lines"]
        assert all("onion" not in x["name"] for x in empty)


def test_two_slots_keep_cooked_when_put_with_ids(tmp_path):
    with _client(tmp_path) as client:
        plan = client.get("/api/plans/current").json()
        saved = client.put(
            f"/api/plans/{plan['id']}/slots",
            json={
                "slots": [
                    {"recipe_id": 1, "day_index": 0, "meal_type": "dinner", "servings": 4},
                    {"recipe_id": 1, "day_index": 1, "meal_type": "dinner", "servings": 4},
                ]
            },
        )
        a, b = saved.json()["slots"]
        client.patch(f"/api/slots/{a['id']}", json={"cooked": True})
        moved = client.put(
            f"/api/plans/{plan['id']}/slots",
            json={
                "slots": [
                    {
                        "id": b["id"],
                        "recipe_id": 1,
                        "day_index": 4,
                        "meal_type": "dinner",
                        "servings": 4,
                    },
                    {
                        "id": a["id"],
                        "recipe_id": 1,
                        "day_index": 5,
                        "meal_type": "dinner",
                        "servings": 4,
                    },
                ]
            },
        )
        slots = moved.json()["slots"]
        assert slots[0]["cooked"] is False
        assert slots[0]["day_index"] == 4
        assert slots[1]["cooked"] is True
        assert slots[1]["day_index"] == 5


def test_explicit_food_dir_is_under_mount(monkeypatch, tmp_path):
    from app.main import _food_roots

    (tmp_path / "food").mkdir()
    monkeypatch.setenv("FOOD_DIR", str(tmp_path / "food"))
    roots = _food_roots()
    assert tmp_path / "food" in roots


def test_food_photo_is_not_spa_html(tmp_path, monkeypatch):
    from app.domain import recipe_photos

    import base64
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    (photo_dir / "sample.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aN1kAAAAASUVORK5CYII="
    ))
    monkeypatch.setenv("FOOD_DIR", str(photo_dir))
    monkeypatch.setattr(recipe_photos, "USE", {"sample.png"})
    with _client(tmp_path) as client:
        res = client.get("/food/sample.png")
        assert res.status_code == 200
        assert "image/png" in res.headers["content-type"]
        assert res.content.startswith(b"\x89PNG")


def _add_catalog(path: Path, slug: str, name: str, copied: bool, photo: str) -> None:
    db = connect()
    ts = now()
    db.execute(
        """INSERT INTO recipes (
            household_id, slug, name, servings, cooking_minutes,
            instructions_json, cookware_json, source_url, provenance_json,
            photo_path, created_at, updated_at
        ) VALUES (NULL, ?, ?, 4, 20, '[]', '[]', '', ?, ?, ?, ?)""",
        (
            slug,
            name,
            '{"instructions_copied_from_third_party": %s}' % ("true" if copied else "false"),
            photo,
            ts,
            ts,
        ),
    )
    db.commit()
    db.close()


def test_catalog_lists_only_rewritten_recipes_with_real_photos(tmp_path):
    _seed(tmp_path)
    _add_catalog(tmp_path, "copied", "Copied steps", True, "food/copied.jpg")
    _add_catalog(tmp_path, "stock", "Stock photo", False, "food/pasta-tomato.jpg")
    _add_catalog(tmp_path, "nophoto", "No photo", False, "")
    with TestClient(create_app()) as client:
        made = client.post(
            "/api/recipes",
            json={"name": "Our own stew", "ingredients": [], "instructions": []},
        )
        assert made.status_code == 200
        recipes = client.get("/api/recipes").json()["recipes"]
        names = [r["name"] for r in recipes]
        assert "Soup" in names
        assert "Our own stew" in names
        assert "Copied steps" not in names
        assert "No photo" not in names
        stock = next(r for r in recipes if r["name"] == "Stock photo")
        assert stock["photo_path"] == ""


def test_suggestions_require_approval_and_keep_feedback(tmp_path, monkeypatch):
    import app.routes as routes

    def suggestions(db, household_id, want):
        return ([{"id": 1, "reasons": []}], "Suggested dinners", {"1": []})

    monkeypatch.setattr(routes, "_suggest_meals", suggestions)
    with _client(tmp_path) as client:
        current = client.get("/api/plans/current").json()
        proposal = client.post("/api/plans", json={"meal_count": 1}).json()
        assert proposal["status"] == "suggested"
        assert client.get(f"/api/plans/{proposal['id']}/grocery").json()["lines"] == []
        assert client.get("/api/plans/current").json()["id"] == current["id"]
        assert client.get("/api/suggestions/current").json()["plan"]["id"] == proposal["id"]
        declined = client.post(f"/api/plans/{proposal['id']}/decision/decline").json()
        assert declined["status"] == "declined"
        assert declined["feedback"] == [{"recipe_id": "1", "liked": False}]
        assert client.get("/api/plans/current").json()["id"] == current["id"]
        assert client.post(f"/api/plans/{proposal['id']}/decision/approve").status_code == 409
        proposal = client.post("/api/plans", json={"meal_count": 1}).json()
        approved = client.post(f"/api/plans/{proposal['id']}/decision/approve").json()
        assert approved["status"] == "active"
        assert approved["decision"] == "approve"
        assert approved["original_recipe_ids"] == [1]
        assert client.get("/api/plans/current").json()["id"] == approved["id"]
        assert client.get("/api/suggestions/current").json()["plan"] is None


def test_suggestion_swaps_and_keeps_own_selections(tmp_path, monkeypatch):
    import app.routes as routes

    with _client(tmp_path) as client:
        db = connect()
        ts = now()
        db.execute("""INSERT INTO recipes (household_id, slug, name, servings, cooking_minutes,
            instructions_json, cookware_json, source_url, provenance_json, photo_path, created_at, updated_at)
            VALUES (NULL, 'pasta', 'Pasta', 2, 20, '[]', '[]', '', '{}', '', ?, ?)""", (ts, ts))
        rid = int(db.lastrowid)
        db.commit()
        db.close()
        monkeypatch.setattr(routes, "_suggest_meals", lambda *args: ([{"id": 1}, {"id": rid}], "Suggestions", {}))
        proposal = client.post("/api/plans", json={"meal_count": 1}).json()
        swapped = client.post(f"/api/plans/{proposal['id']}/swap/{proposal['slots'][0]['id']}").json()
        assert swapped["slots"][0]["recipe_id"] == rid
        assert swapped["changes"][0]["from"] == 1
        assert swapped["feedback"][0] == {"recipe_id": "1", "liked": False}
        assert client.post(f"/api/plans/{proposal['id']}/swap/{proposal['slots'][0]['id']}").status_code == 409
        active = client.get("/api/plans/current").json()
        client.put(f"/api/plans/{active['id']}/slots", json={"slots": [{"recipe_id": 1, "servings": 4}]})
        filled = client.post("/api/plans", json={"meal_count": 1, "keep_current": True}).json()
        assert [s["recipe_id"] for s in filled["slots"]] == [1, rid]
        assert filled["suggested_recipe_ids"] == [rid]
        assert client.post(f"/api/plans/{filled['id']}/swap/{filled['slots'][0]['id']}").status_code == 409


def test_resize_suggestion_preserves_plan_and_does_not_add_dislikes(tmp_path, monkeypatch):
    import app.routes as routes
    with _client(tmp_path) as client:
        db = connect()
        ids = [1]
        for index in range(5):
            ts = now()
            cur = db.execute("""INSERT INTO recipes (household_id, slug, name, servings, cooking_minutes,
                instructions_json, cookware_json, source_url, provenance_json, photo_path, created_at, updated_at)
                VALUES (NULL, ?, ?, 4, 20, '[]', '[]', '', '{}', '', ?, ?)""", (f"resize-{index}", f"Meal {index}", ts, ts))
            ids.append(int(cur.lastrowid))
        db.commit()
        db.close()
        monkeypatch.setattr(routes, "_suggest_meals", lambda *args: ([{"id": rid} for rid in ids], "Suggestions", {}))
        active = client.get("/api/plans/current").json()
        plan = client.post("/api/plans", json={"meal_count": 4}).json()
        assert len(plan["slots"]) == 4
        expanded = client.post(f"/api/plans/{plan['id']}/resize", json={"meal_count": 5}).json()
        assert [s["id"] for s in expanded["slots"][:4]] == [s["id"] for s in plan["slots"]]
        shrunk = client.post(f"/api/plans/{plan['id']}/resize", json={"meal_count": 2}).json()
        assert len(shrunk["slots"]) == 2
        assert shrunk["feedback"] == []
        assert len(shrunk["count_changes"]) == 2
        assert client.get("/api/plans/current").json()["id"] == active["id"]
        approved = client.post(f"/api/plans/{plan['id']}/decision/approve").json()
        assert len(approved["count_changes"]) == 2
        assert client.post(f"/api/plans/{plan['id']}/resize", json={"meal_count": 4}).status_code == 409


def test_real_suggestions_load_contextual_feedback(tmp_path, monkeypatch):
    import json
    import app.routes as routes
    monkeypatch.setattr(routes, "snapshots_for_accounts", lambda accounts: [])
    monkeypatch.setattr(routes, "_candidate_meals", lambda *args: [{"id": 1, "keys": ["1"], "name": "Chicken soup", "ingredients": ["chicken", "carrot"], "tags": [], "cooking_minutes": 20}])
    with _client(tmp_path) as client:
        current = client.get("/api/plans/current").json()
        db = connect()
        db.execute("UPDATE plans SET suggestion_json = ? WHERE id = ?", (json.dumps({"decision": "decline", "suggested_recipe_ids": [1], "changes": []}), current["id"]))
        db.commit()
        db.close()
        response = client.get("/api/suggestions/recipes")
        assert response.status_code == 200
        assert 1 in response.json()["recipe_ids"]


def test_suggestion_capabilities_and_fresh_meals(tmp_path, monkeypatch):
    import app.routes as routes
    with _client(tmp_path) as client:
        capabilities = client.get("/api/suggestions/capabilities").json()
        assert capabilities == {"version": 2, "review": True, "resize": True, "swap": True}
        db = connect()
        ts = now()
        cur = db.execute("""INSERT INTO recipes (household_id, slug, name, servings, cooking_minutes,
            instructions_json, cookware_json, source_url, provenance_json, photo_path, created_at, updated_at)
            VALUES (NULL, 'fresh', 'Fresh dinner', 4, 20, '[]', '[]', '', '{}', '', ?, ?)""", (ts, ts))
        fresh_id = int(cur.lastrowid)
        db.commit()
        db.close()
        active = client.get("/api/plans/current").json()
        client.put(f"/api/plans/{active['id']}/slots", json={"slots": [{"recipe_id": 1, "servings": 4}]})
        monkeypatch.setattr(routes, "_suggest_meals", lambda *args: ([{"id": 1}, {"id": fresh_id}], "Suggestions", {}))
        proposal = client.post("/api/plans", json={"meal_count": 1}).json()
        assert proposal["slots"][0]["recipe_id"] == fresh_id
        assert proposal["suggested_recipe_ids"] == [fresh_id]


def test_recipe_list_respects_diet_and_avoid_filters(tmp_path):
    _seed(tmp_path)
    _add_catalog(tmp_path, "turkey-chili", "Turkey Chili", False, "food/turkey-chili.jpg")
    _add_catalog(tmp_path, "garden-bowl", "Garden Bowl", False, "food/garden-bowl.jpg")
    _add_catalog(tmp_path, "peanut-noodles", "Peanut Noodles", False, "food/peanut-noodles.jpg")
    db = connect()
    db.execute("INSERT INTO ingredients (canonical_name, aliases_json, aisle) VALUES ('salmon fillet', '[]', 'meat')")
    db.execute("INSERT INTO ingredients (canonical_name, aliases_json, aisle) VALUES ('peanut butter', '[]', 'pantry')")
    garden = db.execute("SELECT id FROM recipes WHERE slug = 'garden-bowl'").fetchone()["id"]
    noodles = db.execute("SELECT id FROM recipes WHERE slug = 'peanut-noodles'").fetchone()["id"]
    salmon = db.execute("SELECT id FROM ingredients WHERE canonical_name = 'salmon fillet'").fetchone()["id"]
    pb = db.execute("SELECT id FROM ingredients WHERE canonical_name = 'peanut butter'").fetchone()["id"]
    db.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id) VALUES (?, ?)", (garden, salmon))
    db.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id) VALUES (?, ?)", (noodles, pb))
    db.commit()
    db.close()
    with TestClient(create_app()) as client:
        names = lambda: {r["name"] for r in client.get("/api/recipes").json()["recipes"]}
        assert {"Turkey Chili", "Garden Bowl", "Peanut Noodles", "Soup"} <= names()

        saved = client.put("/api/household", json={"prefs": {"filters": {
            "diets": ["omnivore", "vegan"], "avoids": ["none"]}}})
        assert saved.status_code == 200
        filters = client.get("/api/household").json()["prefs"]["filters"]
        assert filters["diets"] == ["vegan"]
        assert filters["avoids"] == []
        shown = names()
        assert "Turkey Chili" not in shown
        assert "Garden Bowl" not in shown  # salmon is in the ingredients, not the name
        assert {"Peanut Noodles", "Soup"} <= shown  # peanut butter is not dairy

        client.put("/api/household", json={"prefs": {"filters": {"diets": [], "avoids": ["fish"]}}})
        shown = names()
        assert "Turkey Chili" in shown
        assert "Garden Bowl" not in shown

        hidden_list = client.get("/api/recipes?hidden=true").json()["recipes"]
        assert hidden_list == []


def test_delete_saved_plans_protects_current_and_other_households(tmp_path):
    with _client(tmp_path) as client:
        current = client.get("/api/plans/current").json()
        assert client.delete(f"/api/plans/{current['id']}").status_code == 409
        draft = client.post("/api/plans", json={"draft": True, "source_plan_id": current["id"]}).json()
        assert client.delete(f"/api/plans/{draft['id']}").status_code == 200
        assert draft["id"] not in [p["id"] for p in client.get("/api/plans").json()["plans"]]
        assert client.get(f"/api/plans/{draft['id']}").status_code == 404
        assert client.delete("/api/plans/1").status_code == 404
        replacement = client.post("/api/plans", json={}).json()
        assert client.delete(f"/api/plans/{current['id']}").status_code == 200
        assert client.get("/api/plans/current").json()["id"] == replacement["id"]


def test_individual_prep_completion_and_whole_task_toggle(tmp_path):
    with _client(tmp_path) as client:
        recipe = client.post("/api/recipes", json={"name": "Prep test", "servings": 4, "instructions": [{"text": "Dice onions."}, {"text": "Mince onions."}]}).json()
        plan = client.get("/api/plans/current").json()
        client.put(f"/api/plans/{plan['id']}/slots", json={"slots": [{"recipe_id": recipe["id"], "servings": 4}]})
        task = client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"][0]
        steps = task["meals"][0]["steps"]
        response = client.put(f"/api/prep/{task['id']}/steps", json={"recipe_id": recipe["id"], "key": steps[0]["key"], "done": True})
        assert response.status_code == 200
        partial = client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"][0]
        assert partial["id"] == task["id"] and partial["done"] is False
        assert [s["done"] for s in partial["meals"][0]["steps"]] == [True, False]
        assert client.put(f"/api/prep/{task['id']}/steps", json={"recipe_id": recipe["id"], "key": "unknown", "done": True}).status_code == 404
        # The iPhone app decodes this body; an empty reply showed its full-screen error.
        assert client.patch(f"/api/prep/{task['id']}", json={"done": True}).json() == {"ok": True}
        complete = client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"][0]
        assert complete["done"] and all(s["done"] for s in complete["meals"][0]["steps"])
        client.put(f"/api/prep/{task['id']}/steps", json={"recipe_id": recipe["id"], "key": steps[0]["key"], "done": False})
        reopened = client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"][0]
        assert reopened["done"] is False
        assert [s["done"] for s in reopened["meals"][0]["steps"]] == [False, True]
        # #21: 👍/👎 with a reason on the whole item, shown back on the task.
        assert client.put(f"/api/prep/{task['id']}/feedback", json={"rating": -1, "reason": "kept_badly"}).status_code == 200
        voted = client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"][0]
        assert (voted["rating"], voted["reason"]) == (-1, "kept_badly")
        assert voted["section"] and voted["item"]
        assert client.put(f"/api/prep/{task['id']}/feedback", json={"rating": -1, "reason": "nope"}).status_code == 422
        client.put(f"/api/prep/{task['id']}/feedback", json={"rating": 0})
        assert client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"][0]["rating"] == 0


def test_searchable_swap_options_and_explicit_replacement(tmp_path, monkeypatch):
    import app.routes as routes
    with _client(tmp_path) as client:
        recipe = client.post("/api/recipes", json={"name": "Lemon chicken", "servings": 4}).json()
        monkeypatch.setattr(routes, "_suggest_meals", lambda *args: ([{"id": 1, "name": "Soup", "reasons": []}, {"id": recipe["id"], "name": "Lemon chicken", "ingredients": ["lemon"], "reasons": []}], "Suggestions", {}))
        proposal = client.post("/api/plans", json={"meal_count": 1}).json()
        slot = proposal["slots"][0]
        options = client.get(f"/api/plans/{proposal['id']}/swap-options/{slot['id']}?q=lemon").json()
        assert [r["id"] for r in options["recipes"]] == [recipe["id"]]
        assert client.post(f"/api/plans/{proposal['id']}/swap/{slot['id']}", json={"recipe_id": 2}).status_code == 409
        swapped = client.post(f"/api/plans/{proposal['id']}/swap/{slot['id']}", json={"recipe_id": recipe["id"]}).json()
        assert swapped["slots"][0]["recipe_id"] == recipe["id"]
        assert swapped["changes"][0]["to"] == recipe["id"]


def test_prep_progress_survives_regrouping_but_changed_steps_reset(tmp_path):
    with _client(tmp_path) as client:
        recipe = client.post("/api/recipes", json={"name": "Chicken dinner", "servings": 4, "instructions": [{"text": "Peel potatoes."}, {"text": "Dice onions."}]}).json()
        plan = client.get("/api/plans/current").json()
        client.put(f"/api/plans/{plan['id']}/slots", json={"slots": [{"recipe_id": recipe["id"], "servings": 4}]})
        task = client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"][0]
        first = task["meals"][0]["steps"][0]
        client.put(f"/api/prep/{task['id']}/steps", json={"recipe_id": recipe["id"], "key": first["key"], "done": True})
        client.patch(f"/api/recipes/{recipe['id']}", json={"name": "Chicken with mashed potatoes"})
        tasks = client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"]
        potato = next(t for t in tasks if t["title"] == "Prep mashed potatoes")
        assert potato["done"] and potato["meals"][0]["steps"][0]["done"]
        client.patch(f"/api/recipes/{recipe['id']}", json={"instructions": [{"text": "Peel and dice potatoes."}, {"text": "Dice onions."}]})
        tasks = client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"]
        potato = next(t for t in tasks if t["title"] == "Prep mashed potatoes")
        assert not potato["done"] and not potato["meals"][0]["steps"][0]["done"]


def test_prep_items_check_off_one_at_a_time(tmp_path):
    with _client(tmp_path) as client:
        client.patch("/api/recipes/1", json={"instructions": [
            {"text": "Dice the onion. Mince the garlic.", "prep": False},
            {"text": "Heat the oven.", "prep": False},
        ]})
        pid = client.get("/api/plans/current").json()["id"]
        client.put(f"/api/plans/{pid}/slots",
                   json={"slots": [{"recipe_id": 1, "day_index": 1, "meal_type": "dinner", "servings": 4}]})
        tasks = {t["title"]: t for t in client.get(f"/api/plans/{pid}/prep").json()["tasks"]}
        assert set(tasks) == {"Prep onion", "Prep garlic"}
        onion = tasks["Prep onion"]
        step = onion["meals"][0]["steps"][0]
        assert step["done"] is False and onion["done"] is False

        checked = client.put(f"/api/prep/{onion['id']}/steps",
                             json={"recipe_id": 1, "key": step["key"], "done": True})
        assert checked.status_code == 200 and checked.json()["done"] is True
        tasks = {t["title"]: t for t in client.get(f"/api/plans/{pid}/prep").json()["tasks"]}
        assert tasks["Prep onion"]["done"] is True
        assert tasks["Prep onion"]["meals"][0]["steps"][0]["done"] is True
        assert tasks["Prep garlic"]["done"] is False

        # Unchecking the whole task clears its items.
        client.patch(f"/api/prep/{onion['id']}", json={"done": False})
        tasks = {t["title"]: t for t in client.get(f"/api/plans/{pid}/prep").json()["tasks"]}
        assert tasks["Prep onion"]["meals"][0]["steps"][0]["done"] is False

        bad = client.put(f"/api/prep/{onion['id']}/steps", json={"recipe_id": 1, "key": "nope", "done": True})
        assert bad.status_code == 404


def test_prep_json_progress_and_legacy_migration(tmp_path):
    import json
    with _client(tmp_path) as client:
        recipe = client.post("/api/recipes", json={"name": "Onion prep", "servings": 4, "instructions": [{"text": "Dice onions."}, {"text": "Mince onions."}]}).json()
        plan = client.get("/api/plans/current").json()
        client.put(f"/api/plans/{plan['id']}/slots", json={"slots": [{"recipe_id": recipe["id"], "servings": 4}]})
        task = client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"][0]
        first, second = task["meals"][0]["steps"]
        # Simulate completion already persisted by the JSON implementation.
        db = connect()
        db.execute("UPDATE prep_tasks SET completed_steps_json = ? WHERE id = ?", (json.dumps([f"{recipe['id']}:{first['key']}"]), task["id"]))
        db.commit()
        db.close()
        payload = {"recipe_id": recipe["id"], "key": second["key"], "done": True}
        assert client.put(f"/api/prep/{task['id']}/steps", json=payload).json()["done"] is True
        assert client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"][0]["done"] is True
        payload["done"] = False
        assert client.put(f"/api/prep/{task['id']}/steps", json=payload).json()["done"] is False
        refreshed = client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"][0]
        assert [s["done"] for s in refreshed["meals"][0]["steps"]] == [True, False]
        # Simulate completion persisted by the other branch's per-step table.
        db = connect()
        db.execute("UPDATE prep_tasks SET done = 0, completed_steps_json = '[]' WHERE id = ?", (task["id"],))
        db.execute("CREATE TABLE prep_step_done (plan_id INTEGER, recipe_id INTEGER, step_key TEXT)")
        db.execute("INSERT INTO prep_step_done (plan_id, recipe_id, step_key) VALUES (?, ?, ?)", (plan["id"], recipe["id"], second["key"]))
        db.commit()
        db.close()
        from app.db.database import migrate_prep_completion
        with connect() as db:
            migrate_prep_completion(db)
            migrate_prep_completion(db)  # safe to run again
            assert db.execute("SELECT to_regclass('prep_step_done') AS name").fetchone()["name"] is None
            db.commit()
        refreshed = client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"][0]
        assert [s["done"] for s in refreshed["meals"][0]["steps"]] == [False, True]
        payload["key"] = second["key"]
        client.put(f"/api/prep/{task['id']}/steps", json=payload)
        assert not any(s["done"] for s in client.get(f"/api/plans/{plan['id']}/prep").json()["tasks"][0]["meals"][0]["steps"])


def test_startup_does_not_import_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("DINNERDESK_IMPORT_CATALOG", "1")
    with _client(tmp_path):
        with connect() as db:
            assert db.execute("SELECT COUNT(*) AS c FROM recipes").fetchone()["c"] == 2


def test_settings_and_taste_lab_share_one_filter_system(tmp_path, monkeypatch):
    """#1: Settings → Filters is the only filter system. Old Taste Lab filters are folded in
    once, then clearing Settings lets meals through even though the Lab snapshot still has them."""
    import app.routes as routes
    import app.taste_lab as taste_lab

    lab = [{
        "account_id": "1",
        "profile": {"diets": ["vegetarian"], "allergens": ["sesame"], "dislikes": ["olives"]},
        "swipes": [],
    }]
    monkeypatch.setattr(taste_lab, "snapshots_for_accounts", lambda accounts: [dict(s) for s in lab])
    monkeypatch.setattr(routes, "snapshots_for_accounts", lambda accounts: [dict(s) for s in lab])
    monkeypatch.setattr(routes, "_candidate_meals", lambda *args: [
        {"id": 1, "keys": ["1"], "name": "Olive tapenade pasta", "ingredients": ["olives", "pasta"], "tags": [], "cooking_minutes": 20},
        {"id": 2, "keys": ["2"], "name": "Sesame chicken", "ingredients": ["chicken", "sesame seeds"], "tags": [], "cooking_minutes": 20},
    ])
    with _client(tmp_path) as client:
        signup = client.post("/api/auth/signup", json={
            "email": "one@example.com", "password": "correct horse battery staple", "household_name": "One"})
        assert signup.status_code == 200

        # The Lab-only filters show up in Settings, so nothing silently stops applying.
        filters = client.get("/api/household").json()["prefs"]["filters"]
        assert filters["diets"] == ["vegetarian"]
        assert filters["allergens"] == ["sesame"]
        assert filters["avoids"] == ["olives"]
        assert client.get("/api/taste").json()["profile"] == {
            "diets": ["vegetarian"], "allergens": ["sesame"], "dislikes": ["olives"]}

        # Taste Lab saves only its keys; cook time from Settings survives.
        client.put("/api/household", json={"prefs": {"filters": {"time": "30"}}})
        client.put("/api/household", json={"prefs": {"filters": {"diets": ["omnivore"], "allergens": [], "avoids": []}}})
        filters = client.get("/api/household").json()["prefs"]["filters"]
        assert filters["time"] == "30"
        assert filters["allergens"] == [] and filters["avoids"] == []
        # Cleared in one place means cleared everywhere: the old Lab profile isn't folded back.
        assert client.get("/api/taste").json()["profile"]["allergens"] == []

        response = client.get("/api/suggestions/recipes")
        assert response.status_code == 200
        assert {1, 2} <= set(response.json()["recipe_ids"])

        # The tour sends diets, avoids and time; an allergy set elsewhere stays.
        client.put("/api/household", json={"prefs": {"filters": {"allergens": ["sesame"]}}})
        client.put("/api/household", json={"prefs": {"filters": {"diets": ["omnivore"], "avoids": [], "time": "any"}}})
        assert client.get("/api/household").json()["prefs"]["filters"]["allergens"] == ["sesame"]
        response = client.get("/api/suggestions/recipes")
        assert 2 not in response.json()["recipe_ids"]


def test_filter_food_search_selects_specific_ingredients(tmp_path):
    with _client(tmp_path) as client:
        created = client.post("/api/recipes", json={
            "name": "Pepper skillet", "servings": 4,
            "ingredients": [{"name": name, "quantity": "1"} for name in
                            ["red bell pepper", "green bell pepper", "yellow bell pepper", "ground turkey", "ground beef"]],
            "instructions": [{"text": "Cook the skillet."}],
        })
        assert created.status_code == 200
        peppers = client.get("/api/filter-items", params={"q": "bell peppers"}).json()["items"]
        assert any("red" in item["name"] for item in peppers)
        assert any("green" in item["name"] for item in peppers)
        assert any("yellow" in item["name"] for item in peppers)
        ground = client.get("/api/filter-items", params={"q": "ground"}).json()["items"]
        assert any("turkey" in item["name"] for item in ground)
        assert any("beef" in item["name"] for item in ground)
        assert client.get("/api/filter-items", params={"q": "not-a-real-food-xyz"}).json()["items"] == []
        assert client.get("/api/filter-items").json()["items"] == []
        selected = peppers[0]["name"]
        saved = client.put("/api/household", json={"prefs": {"filters": {"allergens": [selected]}}}).json()
        assert selected in saved["prefs"]["filters"]["allergens"]
        assert selected in client.get("/api/household").json()["prefs"]["filters"]["allergens"]


def test_unknown_api_requests_say_what_happened(tmp_path, caplog):
    """#2: a request no route takes gets a clear JSON answer and a log line with the app build,
    instead of the website catch-all turning it into a bare 405."""
    import logging
    client = _client(tmp_path)
    with caplog.at_level(logging.WARNING, logger="dinnerdesk.api"):
        missing = client.post("/api/no-such-route", headers={"X-Dinnerdesk-App": "ios 1.0 (7)"})
        wrong = client.delete("/api/health")
        included = client.post("/api/recipes/1")
        auth = client.patch("/api/auth/status")
    assert missing.status_code == 404
    assert missing.json() == {"error": "not_found", "detail": "route", "method": "POST", "path": "/api/no-such-route"}
    assert wrong.status_code == 405
    assert wrong.json()["allowed"] == ["GET"]
    assert wrong.headers["allow"] == "GET"
    assert included.status_code == 405
    assert "GET" in included.json()["allowed"] and "POST" not in included.json()["allowed"]
    assert auth.status_code == 405 and auth.json()["allowed"] == ["GET"]
    assert "POST /api/no-such-route -> 404" in caplog.text and "ios 1.0 (7)" in caplog.text
    assert client.get("/api/health").json() == {"ok": True}  # real routes still win
