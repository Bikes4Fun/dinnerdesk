"""Catalog sync rules that need no database: paths, uploads, matching and merging."""
import hashlib
import json

import pytest

from app.domain.catalog_sync import (
    BadPath, check_upload, content_differences, file_hashes, is_server_owned, merge_photo_list,
    merge_recipe_file, safe_rel, steps_from_db, tags_match,
)

SKIP = {"mealime", "allrecipes", "customizable_template"}
UPLOAD = "admin-upload-" + "a" * 32 + ".jpg"


@pytest.mark.parametrize("rel", [
    "", "data", "/etc/passwd", "data/../x.json", "data/.hidden.json", "food/sub/x.jpg",
    "food/x.exe", "data/run.py", "other/x.json", "data/recipes/../../x.json",
])
def test_sync_refuses_paths_outside_the_catalog(rel):
    with pytest.raises(BadPath):
        safe_rel(rel)


def test_sync_accepts_catalog_paths():
    assert safe_rel("data/recipes/1606.json") == ("data", "recipes/1606.json")
    assert safe_rel("food/1606_taco.png") == ("food", "1606_taco.png")


def test_admin_tool_files_belong_to_the_server():
    assert is_server_owned("data/ingredient_normalization_answers.json")
    assert is_server_owned(f"food/{UPLOAD}")
    assert not is_server_owned("data/recipes/1606.json")
    assert not is_server_owned("food/1606_taco.png")


def test_upload_must_be_complete_real_and_valid():
    body = b'{"use": []}'
    check_upload("data/recipe_photos.json", body, hashlib.sha256(body).hexdigest())
    with pytest.raises(BadPath, match="checksum"):
        check_upload("data/recipe_photos.json", body, "0" * 64)
    pointer = b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 10\n"
    with pytest.raises(BadPath, match="LFS"):
        check_upload("food/x.png", pointer, hashlib.sha256(pointer).hexdigest())
    with pytest.raises(BadPath, match="admin tools"):
        check_upload(f"food/{UPLOAD}", b"x", hashlib.sha256(b"x").hexdigest())
    broken = b'{"use": ['
    with pytest.raises(ValueError):
        check_upload("data/recipe_photos.json", broken, hashlib.sha256(broken).hexdigest())


def test_hashes_skip_hidden_files_and_reuse_the_cache(tmp_path):
    (tmp_path / "recipes").mkdir()
    (tmp_path / "recipes" / "1.json").write_text("{}")
    (tmp_path / ".x.json.tmp").write_text("partial")
    cache: dict = {}
    first = file_hashes(tmp_path, cache)
    assert first == {"recipes/1.json": hashlib.sha256(b"{}").hexdigest()}
    assert file_hashes(tmp_path, cache) == first and len(cache) == 1


def _file():
    return {
        "slug": "beef-taco-salad", "name": "Beef Taco Salad", "servings": 4, "cooking_minutes": 35,
        "ingredients": [{"name": "cheddar cheese", "quantity": "½ (8 oz) block"}],
        "instructions": [{"step": "Shred the cheddar.", "ingredients_for_step": "½ (8 oz) block cheddar cheese"}],
        "cookware": ["grater"], "tags": ["mealime", "taco"], "photo_path": "food/1606_beef.jpg",
        "source_url": "https://www.mealime.com/recipes/x/1606",
    }


def test_database_steps_read_in_the_file_format():
    db = json.dumps([{"text": "Shred it.", "ings": "cheese", "prep": True}, "Serve."])
    assert steps_from_db(db) == [
        {"step": "Shred it.", "ingredients_for_step": "cheese", "prep": True},
        {"step": "Serve.", "ingredients_for_step": ""},
    ]


def test_spacing_and_case_are_not_differences():
    f = _file()
    db = {**f, "name": " Beef  taco salad ", "servings": "4", "cooking_minutes": 35,
          "instructions": [{"step": "Shred the cheddar.", "ingredients_for_step": "½ (8 oz) block cheddar  cheese"}],
          "ingredients": [{"name": "Cheddar Cheese", "quantity": "½ (8 oz) block"}], "cookware": ["Grater"]}
    assert content_differences(f, db) == ["name"]  # a recipe name's capitals do count
    db["name"] = "Beef Taco Salad"
    assert content_differences(f, db) == []


def test_real_edits_are_differences():
    f = _file()
    db = {**f, "name": "Pork Taco Salad", "servings": 6,
          "ingredients": [{"name": "pork shoulder", "quantity": "2 lb"}]}
    assert content_differences(f, db) == ["name", "servings", "ingredients"]


def test_tags_compare_without_source_tags():
    assert tags_match(["mealime", "taco"], ["taco"], SKIP)
    assert not tags_match(["taco"], ["taco", "salad"], SKIP)


def test_pull_writes_only_what_an_admin_edited():
    f = _file()
    server = {
        "admin_edited": {"content": True, "tags": True, "photo": False},
        "content": {**{k: f[k] for k in ("servings", "cooking_minutes", "instructions", "cookware")},
                    "name": "Shredded Pork Taco Salad",
                    "ingredients": [{"name": "pork shoulder", "quantity": "2 lb"}]},
        "tags": ["taco", "salad"], "photo_path": "food/other.jpg", "dev_notes": "",
    }
    out, changed = merge_recipe_file(f, server, SKIP)
    assert changed == ["name", "ingredients", "tags"]
    assert out["name"] == "Shredded Pork Taco Salad"
    assert out["tags"] == ["mealime", "taco", "salad"]  # the source tag stays in the file
    assert out["photo_path"] == "food/1606_beef.jpg"  # photo wasn't admin-edited
    assert out["source_url"] == f["source_url"] and out["slug"] == f["slug"]


def test_pull_of_unedited_recipe_changes_nothing():
    f = _file()
    server = {"admin_edited": {}, "content": {"name": "Different"}, "tags": [], "photo_path": "", "dev_notes": ""}
    assert merge_recipe_file(f, server, SKIP) == (f, [])


def test_photo_list_gains_uploads_and_loses_deleted_photos():
    photos = {"use": [
        {"file": "1606_beef.jpg", "recipe_id": 1606, "ai_generated": True},
        {"file": "1606_pork.png", "recipe_id": 1606},
        {"file": "1606_beef.jpg", "recipe_id": 99},  # the same file on another recipe stays
    ]}
    recipes = [{"archive_id": "1606", "photo_path": f"food/{UPLOAD}", "gallery": ["food/1606_pork.png"],
                "removed_photos": ["food/1606_beef.jpg"]}]
    out, notes = merge_photo_list(photos, recipes)
    assert [(e["file"], e["recipe_id"]) for e in out["use"]] == [
        ("1606_pork.png", 1606), ("1606_beef.jpg", 99), (UPLOAD, 1606)]
    assert len(notes) == 2
    again, notes = merge_photo_list(out, recipes)
    assert again == out and notes == []


def test_photo_list_reloads_in_place(tmp_path, monkeypatch):
    from app.domain import recipe_photos
    from app.domain.recipe_photos import GALLERY, USE, catalog_gallery
    (tmp_path / "recipe_photos.json").write_text(json.dumps({"use": [
        {"file": "7_new.png", "recipe_id": 7}, {"file": "shared.png", "recipe_id": None}]}))
    monkeypatch.setenv("DINNERDESK_CATALOG_DIR", str(tmp_path))
    try:
        recipe_photos.reload()
        assert catalog_gallery("7") == ["food/7_new.png"]
        assert USE is recipe_photos.USE and "shared.png" in USE  # same table objects, new contents
        assert GALLERY == {"7": ["7_new.png"]}
    finally:
        monkeypatch.undo()
        recipe_photos.reload()


def test_pull_writes_an_admin_retire_into_the_file():
    f = _file()
    server = {"admin_edited": {"retired": True}, "retired": True, "content": {}, "tags": [],
              "photo_path": "", "dev_notes": ""}
    out, changed = merge_recipe_file(f, server, SKIP)
    assert out["retired"] is True and changed == ["retired"]
    back = {**server, "retired": False}
    out2, changed2 = merge_recipe_file(out, back, SKIP)
    assert out2["retired"] is False and changed2 == ["retired"]
    # Not admin-edited: the file's own value stays.
    assert merge_recipe_file(f, {**server, "admin_edited": {}}, SKIP) == (f, [])


@pytest.mark.parametrize("reviewed", [True, False])
def test_pull_preserves_admin_recipe_review(reviewed):
    file_data = {**_file(), 'reviewed': not reviewed}
    server = {'admin_edited': {'reviewed': True}, 'reviewed': reviewed}
    out, changed = merge_recipe_file(file_data, server, SKIP)
    assert out['reviewed'] is reviewed and changed == ['reviewed']
    assert merge_recipe_file(out, server, SKIP) == (out, [])
    assert merge_recipe_file(file_data, {**server, 'admin_edited': {}}, SKIP) == (file_data, [])


@pytest.mark.parametrize('field', ['to_edit', 'delete_requested'])
@pytest.mark.parametrize('value', [True, False])
def test_pull_preserves_admin_workflow_fields(field, value):
    original = {**_file(), field: not value}
    server = {'admin_edited': {field: True}, field: value}
    merged, changed = merge_recipe_file(original, server, SKIP)
    assert merged[field] is value and changed == [field]
    assert merge_recipe_file(merged, server, SKIP) == (merged, [])
    assert merge_recipe_file(original, {**server, 'admin_edited': {}}, SKIP) == (original, [])
