"""The deploy step: dd_support rewrites with one of our photos reach the database."""
import json
import shutil
import subprocess
from pathlib import Path

from app.db.catalog import catalog_records, ready, with_photo
from app.domain.recipe_photos import our_photo_entries


def _catalog(tmp_path, monkeypatch, recipes=(), rewritten=(), photos=(), files=()):
    """A dd_support-shaped tree: catalog/dinnerdesk/{data,food}. `rewritten` recipes are put in the
    one recipe folder the way recipe_rewrite/add_to_catalog.py puts them there."""
    data = tmp_path / "catalog" / "dinnerdesk" / "data"
    food = tmp_path / "catalog" / "dinnerdesk" / "food"
    shutil.copytree(Path(__file__).parent / "fixtures" / "catalog", data)  # startup seeds read these
    for d in (data / "recipes", food):
        d.mkdir(parents=True, exist_ok=True)
    for r in recipes:
        (data / "recipes" / f"{r['id']}.json").write_text(json.dumps(r))
    for _name, r in rewritten:
        (data / "recipes" / f"{r['id']}.json").write_text(json.dumps(r))
    (data / "recipe_photos.json").write_text(json.dumps({"use": list(photos)}))
    for f in files:
        (food / f).write_bytes(b"jpg")
    monkeypatch.setenv("DINNERDESK_CATALOG_DIR", str(data))
    monkeypatch.setenv("FOOD_DIR", str(food))
    return data


def test_recipe_site_photos_are_never_ours():
    entries = our_photo_entries({"use": [
        {"file": "1_soup_ai-generated.jpg", "recipe_id": 1, "owner": "Dinnerdesk"},
        {"file": "2 soup.png", "recipe_id": 2, "credit": "Mealime"},
        "mealime-3.png",
        {"file": "4_photo-by-deanna.jpg", "recipe_id": 4, "credit": "Deanna"},
    ]})
    assert entries == [("1_soup_ai-generated.jpg", 1), ("4_photo-by-deanna.jpg", 4)]


def test_new_rewrite_with_our_photo_is_ready(tmp_path, monkeypatch):
    from app.db.catalog import catalog_photos

    _catalog(
        tmp_path, monkeypatch,
        recipes=[{"id": 1, "slug": "old", "instructions_copied_from_third_party": False,
                  "photo_path": "food/1.jpg"}],
        rewritten=[
            ("allrecipes-7.json", {"id": 7, "slug": "new-7", "instructions_copied_from_third_party": False}),
            ("mealime-8.json", {"id": 8, "slug": "no-photo", "instructions_copied_from_third_party": False}),
            ("mealime-9.json", {"id": 9, "slug": "mealime-photo", "instructions_copied_from_third_party": False}),
        ],
        photos=[{"file": "1.jpg", "recipe_id": 1}, {"file": "7_new_ai-generated.jpg", "recipe_id": 7},
                {"file": "9 mealime.png", "recipe_id": 9, "credit": "Mealime"}],
        files=["1.jpg", "7_new_ai-generated.jpg", "9 mealime.png"],
    )
    photos = catalog_photos()
    records = {r["slug"]: with_photo(r, photos) for r in catalog_records()}
    assert records["new-7"]["photo_path"] == "food/7_new_ai-generated.jpg"
    assert ready(records["new-7"], photos) and ready(records["old"], photos)
    assert not ready(records["no-photo"], photos)
    assert not ready(records["mealime-photo"], photos)


def test_only_the_catalog_folder_is_read(tmp_path, monkeypatch):
    """Recipes come from catalog/dinnerdesk/data/recipes only; old side folders are ignored."""
    _catalog(tmp_path, monkeypatch, recipes=[{"id": 1, "slug": "one", "name": "One"}])
    side = tmp_path / "recipes" / "rewritten"
    side.mkdir(parents=True)
    (side / "allrecipes-2.json").write_text(json.dumps({"id": 2, "slug": "two", "name": "Two"}))
    assert [r["slug"] for r in catalog_records()] == ["one"]


def test_unlisted_or_missing_photo_is_not_ready(tmp_path, monkeypatch):
    from app.db.catalog import catalog_photos

    _catalog(
        tmp_path, monkeypatch,
        recipes=[
            {"id": 1, "slug": "unlisted", "photo_path": "food/stray.jpg"},
            {"id": 2, "slug": "missing-file", "photo_path": "food/2.jpg"},
        ],
        photos=[{"file": "2.jpg", "recipe_id": 2}],
        files=["stray.jpg"],
    )
    photos = catalog_photos()
    for r in catalog_records():
        assert not ready(with_photo(r, photos), photos)


def test_deploy_never_touches_git(monkeypatch):
    """The catalog sync is the only way files reach the server; a deploy only imports them."""
    import app.db.deploy_catalog as deploy

    assert not hasattr(deploy, "sync_dd_support")
    calls = []
    monkeypatch.setattr(deploy.subprocess, "run", lambda *a, **k: calls.append(a), raising=False)
    monkeypatch.delenv("DINNERDESK_IMPORT_CATALOG", raising=False)
    deploy.main()
    assert calls == []


def test_import_adds_rewrite_with_our_photo_and_applies_edits(tmp_path, monkeypatch):
    from app.db.catalog import import_recipes
    from app.db.database import connect
    from tests.test_api import _client

    data = _catalog(
        tmp_path, monkeypatch,
        rewritten=[("allrecipes-7.json", {"id": 7, "slug": "new-7", "name": "New", "servings": 2,
                                          "instructions_copied_from_third_party": False})],
        photos=[{"file": "7_new_ai-generated.jpg", "recipe_id": 7}],
        files=["7_new_ai-generated.jpg"],
    )
    (data / "recipes" / "1.json").write_text(json.dumps(
        {"id": 1, "slug": "copied", "servings": 2, "instructions_copied_from_third_party": True}))
    with _client(tmp_path):
        db = connect()
        import_recipes(db, {})
        db.commit()
        row = db.execute("SELECT name, photo_path FROM recipes WHERE slug = 'new-7'").fetchone()
        assert row["name"] == "New" and row["photo_path"] == "food/7_new_ai-generated.jpg"
        assert not db.execute("SELECT 1 FROM recipes WHERE slug = 'copied'").fetchone()

        (data / "recipes" / "7.json").write_text(json.dumps(
            {"id": 7, "slug": "new-7", "name": "Renamed", "servings": 2,
             "instructions_copied_from_third_party": False}))
        import_recipes(db, {})
        db.commit()
        assert db.execute("SELECT name FROM recipes WHERE slug = 'new-7'").fetchone()["name"] == "Renamed"
        db.close()
