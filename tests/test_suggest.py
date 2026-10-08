from app.domain.suggest import pick_suggestions, score_recipe, shop_set


def test_shop_set_drops_staples():
    shop = shop_set(
        ["salt", "chicken breast", "olive oil", "onion"],
        {},
    )
    assert shop == {"chicken breast", "yellow onion"}


def test_never_shop_item_is_ignored():
    shop = shop_set(
        ["chicken breast", "yellow onion"],
        {},
        skip={"yellow onion"},
    )
    assert shop == {"chicken breast"}
    on_hand, on_hand_why = score_recipe({"chicken breast"}, {"chicken breast"}, set(), False, False)
    ignored, ignored_why = score_recipe(shop, set(), set(), False, False)
    assert on_hand > ignored
    assert "uses 1 from pantry" in on_hand_why
    assert "uses 1 from pantry" not in ignored_why


def test_pantry_overlap_beats_all_new():
    pantry = {"onion", "garlic", "rice"}
    a, _ = score_recipe({"onion", "garlic", "rice"}, pantry, set(), False, False)
    b, _ = score_recipe({"salmon", "asparagus", "cream"}, pantry, set(), False, False)
    assert a > b


def test_greedy_add_ons_reuse_plan_ingredients():
    recipes = [
        {"id": 1, "name": "A", "ingredients": ["chicken breast", "rice", "onion"], "tags": []},
        {"id": 2, "name": "B", "ingredients": ["chicken breast", "rice", "broccoli"], "tags": []},
        {"id": 3, "name": "C", "ingredients": ["shrimp", "coconut milk", "lime"], "tags": []},
    ]
    picked = pick_suggestions(
        recipes,
        pantry=set(),
        plan_ings={"chicken breast", "rice"},
        favorites=set(),
        aliases={},
        want=2,
    )
    assert picked[0]["id"] in {1, 2}
    assert {p["id"] for p in picked} != {3}


def test_favorites_boost():
    recipes = [
        {"id": 1, "name": "New", "ingredients": ["shrimp", "lime"], "tags": []},
        {"id": 2, "name": "Loved", "ingredients": ["shrimp", "lime"], "tags": []},
    ]
    picked = pick_suggestions(
        recipes,
        pantry=set(),
        plan_ings=set(),
        favorites={2},
        aliases={},
        want=1,
    )
    assert picked[0]["id"] == 2
    assert "favorite" in picked[0]["reasons"]


def test_swap_counts_as_the_replacement():
    recipes = [
        {"id": 1, "name": "Thighs", "ingredients": ["chicken thighs"], "tags": []},
        {"id": 2, "name": "Tofu", "ingredients": ["tofu"], "tags": []},
    ]
    picked = pick_suggestions(
        recipes,
        pantry={"chicken breast"},
        plan_ings=set(),
        favorites=set(),
        aliases={},
        overrides={"chicken thighs": "chicken breast"},
        want=1,
    )
    assert picked[0]["id"] == 1
    assert "uses 1 from pantry" in picked[0]["reasons"]


def test_to_try_beats_an_equal_meal():
    recipes = [
        {"id": 1, "name": "New", "ingredients": ["shrimp", "lime"], "tags": []},
        {"id": 2, "name": "Saved", "ingredients": ["shrimp", "lime"], "tags": []},
    ]
    picked = pick_suggestions(
        recipes,
        pantry=set(),
        plan_ings=set(),
        favorites=set(),
        aliases={},
        want=1,
        to_try={2},
    )
    assert picked[0]["id"] == 2
    assert "to try" in picked[0]["reasons"]


def test_to_try_with_pantry_beats_to_try_that_needs_a_new_shop():
    recipes = [
        {"id": 1, "name": "Fits", "ingredients": ["chicken breast", "rice"], "tags": []},
        {"id": 2, "name": "New shop", "ingredients": ["shrimp", "coconut milk"], "tags": []},
    ]
    picked = pick_suggestions(
        recipes,
        pantry={"chicken breast", "rice"},
        plan_ings=set(),
        favorites=set(),
        aliases={},
        want=2,
        to_try={1, 2},
    )
    assert [row["id"] for row in picked] == [1, 2]
    assert "uses 2 from pantry" in picked[0]["reasons"]


def test_later_to_try_reuses_the_plan():
    recipes = [
        {"id": 1, "name": "First", "ingredients": ["chicken breast", "rice"], "tags": []},
        {"id": 2, "name": "Shares", "ingredients": ["chicken breast", "broccoli"], "tags": []},
        {"id": 3, "name": "Separate", "ingredients": ["shrimp", "lime"], "tags": []},
    ]
    picked = pick_suggestions(
        recipes,
        pantry={"chicken breast"},
        plan_ings=set(),
        favorites=set(),
        aliases={},
        want=2,
        to_try={1, 2, 3},
    )
    assert [row["id"] for row in picked] == [1, 2]


def test_reuse_reason_names_the_plan():
    score, reasons = score_recipe({"rice"}, set(), {"rice"}, False, False)
    assert score > 0
    assert "shares 1 with this plan" in reasons
