"""The deploy step: dd_support rewrites with one of our photos reach the database."""
import json
import shutil
import subprocess
from pathlib import Path

from app.db.catalog import catalog_records, ready, with_photo
from app.domain.recipe_photos import our_photo_entries


def _catalog(tmp_path, monkeypatch, recipes=(), rewritten=(), photos=(), files=()):
    """A dd_support-shaped tree: catalog/dinnerdesk/{data,food} and recipes/rewritten."""
    data = tmp_path / "catalog" / "dinnerdesk" / "data"
    food = tmp_path / "catalog" / "dinnerdesk" / "food"
    rw = tmp_path / "recipes" / "rewritten"
    shutil.copytree(Path(__file__).parent / "fixtures" / "catalog", data)  # startup seeds read these
    for d in (data / "recipes", food, rw):
        d.mkdir(parents=True, exist_ok=True)
    for r in recipes:
        (data / "recipes" / f"{r['id']}.json").write_text(json.dumps(r))
    for name, r in rewritten:
        (rw / name).write_text(json.dumps(r))
    (data / "recipe_photos.json").write_text(json.dumps({"use": list(photos)}))
    for f in files:
        (food / f).write_bytes(b"jpg")
    monkeypatch.setenv("DINNERDESK_CATALOG_DIR", str(data))
    monkeypatch.setenv("FOOD_DIR", str(food))
    monkeypatch.delenv("DINNERDESK_REWRITTEN_DIR", raising=False)
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


def test_catalog_copy_wins_once_rewritten(tmp_path, monkeypatch):
    _catalog(
        tmp_path, monkeypatch,
        recipes=[
            {"id": 1, "slug": "edited", "name": "Edited in catalog", "instructions_copied_from_third_party": False},
            {"id": 2, "slug": "copied", "name": "Copied", "instructions": ["theirs"],
             "instructions_copied_from_third_party": True},
        ],
        rewritten=[
            ("allrecipes-1.json", {"id": 1, "name": "Older rewrite", "instructions_copied_from_third_party": False}),
            ("allrecipes-2.json", {"id": 2, "instructions": ["ours"], "instructions_copied_from_third_party": False}),
        ],
    )
    records = {r["slug"]: r for r in catalog_records()}
    assert records["edited"]["name"] == "Edited in catalog"
    assert records["copied"]["instructions"] == ["ours"]
    assert records["copied"]["name"] == "Copied"
    assert not records["copied"]["instructions_copied_from_third_party"]


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


def test_deploy_pulls_dd_support_updates(tmp_path, monkeypatch):
    from app.db.deploy_catalog import sync_dd_support

    origin = tmp_path / "origin"
    (origin / "catalog" / "dinnerdesk" / "data").mkdir(parents=True)
    (origin / "references").mkdir()
    (origin / "references" / "big.bin").write_text("not needed on Railway")
    recipe = origin / "catalog" / "dinnerdesk" / "data" / "1.json"
    recipe.write_text("v1")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.test"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(origin)], check=True)
    subprocess.run([*git, "-C", str(origin), "add", "-A"], check=True)
    subprocess.run([*git, "-C", str(origin), "commit", "-qm", "one"], check=True)

    target = tmp_path / "volume" / "dd_support"
    monkeypatch.setenv("DD_SUPPORT_REPO", f"file://{origin}")
    monkeypatch.setenv("DD_SUPPORT_DIR", str(target))
    monkeypatch.delenv("DD_SUPPORT_TOKEN", raising=False)
    assert sync_dd_support()
    copy = target / "catalog" / "dinnerdesk" / "data" / "1.json"
    assert copy.read_text() == "v1"
    assert not (target / "references").exists()

    recipe.write_text("v2")
    subprocess.run([*git, "-C", str(origin), "commit", "-qam", "two"], check=True)
    assert sync_dd_support()
    assert copy.read_text() == "v2"


def test_deploy_without_repo_does_nothing(monkeypatch):
    from app.db.deploy_catalog import sync_dd_support

    monkeypatch.delenv("DD_SUPPORT_REPO", raising=False)
    assert not sync_dd_support()


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
