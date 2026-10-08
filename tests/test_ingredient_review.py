import json

from fastapi.testclient import TestClient

from app.domain.ingredient_review import (
    broad_key,
    build_proposals,
    collect_flagged_recipes,
    ingredient_core,
    load_answers,
    resolve_group_audit,
    review_groups,
    save_answers,
    save_group_answer,
    save_group_audit,
)
from app.main import create_app


def _login_admin(client):
    res = client.post(
        "/api/auth/signup",
        json={
            "email": "dtzecha@gmail.com",
            "password": "correct horse battery staple",
            "household_name": "Dev",
        },
    )
    assert res.status_code == 200


def _recipe(root, source_dir, recipe_id, name, ingredients):
    path = root / "data" / source_dir / "recipes" / f"{recipe_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "id": recipe_id,
                "slug": str(recipe_id),
                "name": name,
                "source_url": f"https://example.com/{recipe_id}",
                "ingredients": ingredients,
            }
        )
    )
    return path


def _fixture(tmp_path):
    save_answers(tmp_path, {"answers": {}, "audits": {}})
    first = _recipe(
        tmp_path,
        "allrecipes_bulk_scrape",
        "a",
        "Basil Pasta",
        [{"quantity": None, "name": "2 tablespoons fresh basil"}],
    )
    second = _recipe(
        tmp_path,
        "mealime_bulk_scrape",
        "b",
        "Tomato Basil",
        [{"quantity": "1 bunch", "name": "basil"}],
    )
    _recipe(
        tmp_path,
        "myplate_bulk_scrape",
        "c",
        "Avocado Toast",
        [{"quantity": None, "name": "2 avocados"}],
    )
    _recipe(
        tmp_path,
        "mealime_bulk_scrape",
        "d",
        "Avocado Salad",
        [{"quantity": "1", "name": "avocado"}],
    )
    _recipe(
        tmp_path,
        "myplate_bulk_scrape",
        "e",
        "Packet Dinner",
        [
            {"quantity": None, "name": "1 sheet aluminum foil"},
            {"quantity": None, "name": "aluminum foil (10x12 inches square)"},
            {"quantity": None, "name": "2 cups boiling water"},
            {"quantity": None, "name": "boiling water (from the pasta)"},
            {"quantity": None, "name": "1/2 cup cheese"},
            {"quantity": None, "name": "1 red pepper"},
        ],
    )
    return first, second


def test_collects_flagged_recipes(tmp_path):
    _fixture(tmp_path)
    rows = collect_flagged_recipes(tmp_path)
    assert {row["ingredient_name"] for row in rows} == {"cheese", "red pepper"}


def test_extracts_name_from_inline_quantity():
    assert ingredient_core("2 tablespoons olive oil, divided", False) == "olive oil"
    assert ingredient_core("1 (14.5 ounces) can diced tomatoes", False) == "diced tomatoes"
    assert ingredient_core("1 can (15.5 oz) low-sodium black beans", False) == (
        "low-sodium black beans"
    )
    assert ingredient_core("(15.5 oz) low-sodium black beans", False) == (
        "low-sodium black beans"
    )
    assert ingredient_core("(15.5 oz) low-sodium black beans", True) == (
        "low-sodium black beans"
    )
    assert ingredient_core("6 large bone-in chicken thighs (about 3 pounds)", False) == (
        "bone-in chicken thighs"
    )
    assert ingredient_core("2 pounds boneless, skinless chicken breast", False) == (
        "boneless skinless chicken breast"
    )
    assert ingredient_core("4 skinless, boneless chicken thighs", False) == (
        "skinless boneless chicken thighs"
    )
    assert ingredient_core("1 large, ripe tomato, cored", False) == "ripe tomato"
    assert ingredient_core("large flour tortillas", True) == "large flour tortillas"
    assert broad_key("red bell peppers") == "red bell pepper"
    assert broad_key("green bell peppers") == "green bell pepper"
    assert broad_key("red bell peppers") != broad_key("green bell peppers")
    assert broad_key("yellow onion") != broad_key("onion")


def test_scans_all_sources_and_skips_plural_only_group(tmp_path):
    _fixture(tmp_path)
    groups = build_proposals(str(tmp_path))

    assert len(groups) == 1
    assert {row["text"] for row in groups[0]["names"]} == {"basil", "fresh basil"}
    assert {recipe["source"] for recipe in groups[0]["recipes"]} == {
        "allrecipes",
        "mealime",
    }
    names = {row["text"]: row for row in groups[0]["names"]}
    assert names["fresh basil"]["recipes"] == [
        {
            "name": "Basil Pasta",
            "source": "allrecipes",
            "source_url": "https://example.com/a",
            "raw": "2 tablespoons fresh basil",
            "ingredient_name": "fresh basil",
        }
    ]
    assert names["basil"]["recipes"][0]["ingredient_name"] == "basil"


def test_answer_is_separate_and_does_not_touch_recipes(tmp_path):
    first, second = _fixture(tmp_path)
    before = {first: first.read_text(), second: second.read_text()}
    group = build_proposals(str(tmp_path))[0]

    save_group_answer(
        tmp_path,
        group["id"],
        "standardize",
        "basil",
        ["basil", "fresh basil"],
    )

    answer = load_answers(tmp_path)["answers"][group["id"]]
    assert answer["target"] == "basil"
    assert answer["status"] == "answered"
    assert {path: path.read_text() for path in before} == before


def test_second_pass_audit_preserves_original_and_tracks_resolution(tmp_path):
    first, second = _fixture(tmp_path)
    before = {first: first.read_text(), second: second.read_text()}
    group = build_proposals(str(tmp_path))[0]
    save_group_answer(
        tmp_path,
        group["id"],
        "standardize",
        "basil",
        ["basil", "fresh basil"],
    )

    save_group_audit(
        tmp_path,
        group["id"],
        "question",
        "Should fresh basil remain distinct?",
        "separate",
        "basil",
        [],
    )
    audit = load_answers(tmp_path)["audits"][group["id"]]
    assert audit["review_status"] == "pending"
    assert audit["original_answer"]["action"] == "standardize"

    resolve_group_audit(tmp_path, group["id"], "re_review")
    assert load_answers(tmp_path)["audits"][group["id"]]["review_status"] == "re_review"

    save_group_answer(tmp_path, group["id"], "separate", "basil", [])
    resolve_group_audit(tmp_path, group["id"], "accepted_suggestion")
    audit = load_answers(tmp_path)["audits"][group["id"]]
    assert audit["original_answer"]["action"] == "standardize"
    assert audit["resolved_answer"]["action"] == "separate"
    assert audit["review_status"] == "resolved"
    assert {path: path.read_text() for path in before} == before


def test_historical_answer_remains_available_for_second_pass(tmp_path):
    _fixture(tmp_path)
    group = build_proposals(str(tmp_path))[0]
    save_answers(
        tmp_path,
        {
            "answers": {
                "old-pepper-group": {
                    "status": "answered",
                    "action": "separate",
                    "target": "black pepper",
                    "names": [],
                    "proposal_snapshot": {
                        "suggested_name": "black pepper",
                        "names": [
                            {"text": "black pepper", "count": 2, "sources": {}},
                            {"text": "green peppers", "count": 1, "sources": {}},
                        ],
                        "recipe_hits": 3,
                    },
                }
            },
            "audits": {},
        },
    )

    historical = next(
        row for row in review_groups(tmp_path) if row["id"] == "old-pepper-group"
    )
    assert historical["historical"] is True
    assert historical["audit"]["verdict"] == "question"


def test_unselected_names_return_to_first_review(tmp_path):
    save_answers(tmp_path, {"answers": {}, "audits": {}})
    for recipe_id, ingredient in enumerate(
        ["thyme", "fresh thyme", "dried thyme", "whole thyme"],
        start=1,
    ):
        _recipe(
            tmp_path,
            "mealime_bulk_scrape",
            recipe_id,
            f"Thyme Recipe {recipe_id}",
            [{"quantity": "1 teaspoon", "name": ingredient}],
        )
    group = build_proposals(str(tmp_path))[0]
    save_group_answer(
        tmp_path,
        group["id"],
        "standardize",
        "fresh thyme",
        ["thyme", "fresh thyme"],
    )

    follow_up = next(row for row in review_groups(tmp_path) if row.get("follow_up"))
    assert follow_up["queue"] == "harder"
    assert follow_up["answer"] == {}
    assert {row["text"] for row in follow_up["names"]} == {
        "dried thyme",
        "whole thyme",
    }


def test_review_api_is_proposal_only(tmp_path, monkeypatch):
    _fixture(tmp_path)
    monkeypatch.setattr("app.routes.ROOT", tmp_path)
    app = create_app()

    with TestClient(app) as client:
        assert client.get("/api/dev/ingredient-review").status_code == 403
        client.post(
            "/api/auth/signup",
            json={
                "email": "you@example.com",
                "password": "correct horse battery staple",
                "household_name": "House",
            },
        )
        assert client.get("/api/dev/ingredient-review").status_code == 403
        client.post("/api/auth/logout")
        _login_admin(client)
        payload = client.get("/api/dev/ingredient-review").json()
        assert payload["proposal_only"] is True
        group = payload["groups"][0]
        response = client.put(
            f"/api/dev/ingredient-review/{group['id']}/answer",
            json={
                "action": "alias",
                "target": "basil",
                "names": ["basil", "fresh basil"],
            },
        )
        assert response.json() == {"ok": True, "proposal_only": True}
        audit_response = client.put(
            f"/api/dev/ingredient-review/{group['id']}/audit",
            json={
                "verdict": "looks_good",
                "reason": "These are the same grocery item.",
                "suggested_names": [],
            },
        )
        assert audit_response.json() == {"ok": True, "proposal_only": True}
        resolution_response = client.put(
            f"/api/dev/ingredient-review/{group['id']}/audit-resolution",
            json={"resolution": "confirmed"},
        )
        assert resolution_response.json() == {"ok": True, "proposal_only": True}
        updated = client.get("/api/dev/ingredient-review").json()
        assert updated["second_review"] == {"total": 1, "resolved": 1}
