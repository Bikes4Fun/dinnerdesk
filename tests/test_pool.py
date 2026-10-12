from app.domain.diet_filter import blocks_for
from app.domain.pool import build_pool, filters_key


def recipe(rid, name, ingredients, **extra):
    return {"id": rid, "keys": [str(rid)], "slug": name.lower().replace(" ", "-"), "name": name,
            "ingredients": ingredients, "tags": [], "cooking_minutes": 20, **extra}


RECIPES = [
    recipe(1, "Cheesy Broccoli Rice", ["broccoli", "rice", "cheddar cheese"]),
    recipe(2, "Vegan Broccoli Rice", ["broccoli", "rice", "nutritional yeast"], variant_of="cheesy-broccoli-rice"),
    recipe(3, "Chicken Rice", ["chicken thighs", "rice"]),
    recipe(4, "Mushroom Tacos", ["mushrooms", "tortillas"]),
    recipe(5, "Peanut Noodles", ["peanut butter", "noodles"]),
]


def ids(meals):
    return [m["id"] for m in meals]


def test_allergies_and_diets_never_reach_either_tier():
    pool = build_pool(RECIPES, blocks_for(["vegan"], ["peanut"]), [], set())
    assert pool.allowed == {2, 4}
    assert ids(pool.meals) + ids(pool.backup_meals) == [2, 4]


def test_avoided_and_hidden_recipes_are_backup_only():
    hidden = [*RECIPES[:3], {**RECIPES[3], "hidden": True}, RECIPES[4]]
    pool = build_pool(hidden, [], blocks_for([], ["chicken"]), set())
    assert 3 in pool.demoted and 4 in pool.demoted
    assert 3 in ids(pool.backup_meals) and 4 in ids(pool.backup_meals)
    assert 3 not in ids(pool.meals) and 4 not in ids(pool.meals)


def test_variant_is_backup_only_when_its_base_already_fits():
    everyone = build_pool(RECIPES, [], [], set())
    assert everyone.variants == {2}
    assert 2 not in ids(everyone.meals)

    dairy_free = build_pool(RECIPES, blocks_for(["dairy-free"], []), [], set())
    assert dairy_free.variants == frozenset()
    assert 2 in ids(dairy_free.meals)  # the cheesy base is blocked, so this is their version


def test_popular_variant_stays_in_priority():
    popular = [RECIPES[0], {**RECIPES[1], "tags": ["popular"]}]
    assert 2 in ids(build_pool(popular, [], [], set()).meals)


def test_own_recipes_always_keep_the_hard_rules():
    own = [recipe(9, "My Chicken Rice", ["chicken"], own=True)]
    pool = build_pool(own, blocks_for(["vegan"], []), blocks_for([], ["chicken"]), set())
    assert ids(pool.meals) == [9]


def test_filters_key_ignores_order_and_case():
    assert filters_key(["Vegan"], ["soy", "egg"], []) == filters_key(["vegan"], ["egg", "soy"], [])
    assert filters_key(["vegan"], [], []) != filters_key(["vegan"], [], ["tofu"])
