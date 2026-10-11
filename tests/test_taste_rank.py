from app.domain.taste_rank import learn, pick_meals, reasons_summary, suggestion_note


def meal(rid, name, ingredients, keys=None, minutes=None, tags=None):
    return {
        "id": rid,
        "keys": keys or [str(rid)],
        "name": name,
        "ingredients": ingredients,
        "tags": tags or [],
        "cooking_minutes": minutes,
    }


def snap(account, swipes=None, dislikes=None, allergens=None, diets=None, plans=None):
    return {
        "account_id": account,
        "profile": {
            "diets": diets or [],
            "dislikes": dislikes or [],
            "allergens": allergens or [],
        },
        "swipes": swipes or [],
        "plans": plans or [],
    }


def pick(recipes, taste, favorites=None, want=1):
    return pick_meals(recipes, taste, set(), favorites or set(), {}, want)


def test_liked_meal_beats_a_similar_one():
    recipes = [
        meal(1, "Tacos", ["beef", "tortilla"], ["a"]),
        meal(2, "Other tacos", ["beef", "tortilla"], ["b"]),
    ]
    taste = learn([snap("1", [{"recipe_id": "a", "liked": True}])], recipes)
    picked = pick(recipes, taste)
    assert picked[0]["id"] == 1
    assert "you liked this" in picked[0]["reasons"]


def test_passed_meal_is_left_out():
    recipes = [
        meal(1, "Tacos", ["beef", "tortilla"], ["a"]),
        meal(2, "Soup", ["carrot", "broth"], ["b"]),
    ]
    taste = learn([snap("1", [{"recipe_id": "b", "liked": False}])], recipes)
    picked = pick(recipes, taste, favorites={2}, want=2)
    assert [row["id"] for row in picked] == [1]


def test_a_pass_from_anyone_wins():
    recipes = [meal(1, "Tacos", ["beef"], ["a"]), meal(2, "Soup", ["carrot"], ["b"])]
    taste = learn(
        [
            snap("1", [{"recipe_id": "a", "liked": True}]),
            snap("2", [{"recipe_id": "a", "liked": False}]),
        ],
        recipes,
    )
    picked = pick(recipes, taste, want=2)
    assert [row["id"] for row in picked] == [2]


def test_swipes_from_earlier_sessions_stay():
    recipes = [
        meal(1, "Tacos", ["beef"], ["a"]),
        meal(2, "Soup", ["carrot"], ["b"]),
    ]
    taste = learn(
        [
            snap("1", [{"recipe_id": "a", "liked": True}]),
            snap("1", [{"recipe_id": "b", "liked": True}]),
        ],
        recipes,
    )
    picked = pick(recipes, taste, want=2)
    liked_ids = {row["id"] for row in picked if "you liked this" in row["reasons"]}
    assert liked_ids == {1, 2}


def test_latest_swipe_replaces_an_older_one():
    recipes = [meal(1, "Tacos", ["beef"], ["a"])]
    taste = learn(
        [
            snap("1", [{"recipe_id": "a", "liked": False}]),
            snap("1", [{"recipe_id": "a", "liked": True}]),
        ],
        recipes,
    )
    assert pick(recipes, taste)[0]["id"] == 1


def test_dislike_and_diet_block():
    recipes = [
        meal(1, "Mushroom soup", ["mushroom", "broth"]),
        meal(2, "Roast chicken", ["chicken", "potato"]),
        meal(3, "Eggplant", ["eggplant"]),
        meal(4, "Tofu bowl", ["tofu", "rice"]),
    ]
    taste = learn(
        [snap("1", dislikes=["mushrooms", "egg"], diets=["vegetarian"])],
        recipes,
    )
    picked = pick(recipes, taste, want=4)
    assert [row["id"] for row in picked] == [3, 4]


def test_similar_ingredients_follow_likes():
    liked = [
        meal(10, "Hummus", ["chickpea", "lemon", "garlic"]),
        meal(11, "Chana", ["chickpea", "tomato", "onion"]),
    ]
    choices = [
        meal(12, "Falafel", ["chickpea", "herbs"]),
        meal(13, "Salmon", ["salmon", "dill"]),
    ]
    taste = learn(
        [snap("1", [{"recipe_id": "10", "liked": True}, {"recipe_id": "11", "liked": True}])],
        liked + choices,
    )
    picked = pick(choices, taste)
    assert picked[0]["id"] == 12
    assert "similar to meals you liked" in picked[0]["reasons"]


def test_count_and_note():
    recipes = [meal(i, f"Meal {i}", [f"ingredient {i}"]) for i in range(1, 6)]
    taste = learn([], recipes)
    picked = pick(recipes, taste, want=2)
    assert len(picked) == 2
    assert suggestion_note(2, taste) == "Suggested 2 meals from your favorites and pantry."
    assert suggestion_note(0, taste) == "No meals matched your tastes. Add meals from Recipes."


def test_public_taste_uses_latest_filters_and_a_later_pass():
    from app.taste_lab import public_taste

    body = public_taste(
        [
            snap("1", [{"recipe_id": "a", "liked": True}], diets=["vegan"]),
            snap("1", [{"recipe_id": "a", "liked": False}], dislikes=["mushrooms"], diets=["vegetarian"]),
        ],
        signed_in=True,
    )
    assert body["signed_in"] is True
    assert body["profile"]["diets"] == ["vegetarian"]
    assert body["profile"]["dislikes"] == ["mushrooms"]
    assert body["passes"] == 1
    assert body["likes"] == 0
    assert body["votes"] == [{"recipe_id": "a", "liked": False}]
    plan = public_taste(
        [snap("1", plans=[{"recipe_ids": ["b"], "verdict": "up"}])],
        signed_in=True,
    )
    assert plan["likes"] == 1
    assert plan["votes"] == [{"recipe_id": "b", "liked": True, "plan": True}]
    assert public_taste([], signed_in=False)["profile"] is None


def test_public_taste_gives_a_guest_their_own_answers():
    """#27: a guest's earlier likes and passes come back so Taste Lab doesn't ask again."""
    from app.taste_lab import public_taste

    body = public_taste(
        [snap("anon:x", [{"recipe_id": "4664", "liked": True}, {"recipe_id": "768", "liked": False}])],
        signed_in=False,
    )
    assert body["signed_in"] is False
    assert body["profile"] is None
    assert body["votes"] == [{"recipe_id": "768", "liked": False}, {"recipe_id": "4664", "liked": True}]
    assert (body["likes"], body["passes"]) == (1, 1)


def test_favorites_when_taste_lab_is_empty():
    recipes = [
        meal(1, "New", ["shrimp", "lime"]),
        meal(2, "Loved", ["shrimp", "lime"]),
    ]
    taste = learn([], recipes)
    assert pick(recipes, taste, favorites={2})[0]["id"] == 2
    assert not taste.from_lab


def test_one_like_finds_a_nearby_meal():
    recipes = [
        meal(1, "Spaghetti", ["pasta", "tomato"], ["a"]),
        meal(2, "Caprese", ["mozzarella cheese", "basil", "bread"], ["b"]),
        meal(3, "Miso soup", ["miso", "seaweed", "tofu"], ["c"]),
    ]
    taste = learn([snap("1", [{"recipe_id": "a", "liked": True}])], recipes)
    picked = pick(recipes, taste, want=3)
    ids = [row["id"] for row in picked]
    assert ids[0] == 1
    assert ids.index(2) < ids.index(3)
    caprese = next(row for row in picked if row["id"] == 2)
    assert "near a meal you liked" in caprese["reasons"]


def test_pasta_like_nudges_polenta():
    recipes = [
        meal(1, "Spaghetti", ["pasta", "tomato"], ["a"]),
        meal(2, "Creamy polenta", ["polenta", "mushroom"], ["b"]),
        meal(3, "Steak", ["steak", "asparagus"], ["c"]),
    ]
    taste = learn([snap("1", [{"recipe_id": "a", "liked": True}])], recipes)
    picked = pick(recipes, taste, want=3)
    ids = [row["id"] for row in picked]
    assert ids.index(2) < ids.index(3)
    polenta = next(row for row in picked if row["id"] == 2)
    assert "another starch, like the pasta you liked" in polenta["reasons"]


def test_another_pasta_beats_polenta():
    recipes = [
        meal(1, "Spaghetti", ["pasta"], ["a"]),
        meal(2, "Penne", ["pasta", "tomato"], ["b"]),
        meal(3, "Creamy polenta", ["polenta", "mushroom"], ["c"]),
    ]
    taste = learn([snap("1", [{"recipe_id": "a", "liked": True}])], recipes)
    picked = pick(recipes, taste, want=3)
    ids = [row["id"] for row in picked]
    assert ids == [1, 2, 3]


def test_chicken_pass_keeps_other_poultry():
    recipes = [
        meal(1, "Roast chicken", ["chicken"], ["a"]),
        meal(2, "Turkey chili", ["turkey"], ["b"]),
        meal(3, "Tofu", ["tofu"], ["c"]),
    ]
    taste = learn([snap("1", [{"recipe_id": "a", "liked": False}])], recipes)
    picked = pick(recipes, taste, favorites={2}, want=2)
    assert [row["id"] for row in picked] == [2, 3]


def test_swap_is_applied_before_likes_count():
    liked = [meal(1, "Thighs", ["chicken thighs"], ["a"])]
    choices = [
        meal(2, "Breasts", ["chicken breast"], ["b"]),
        meal(3, "Tofu", ["tofu"], ["c"]),
    ]
    swaps = {"chicken thighs": "chicken breast"}
    taste = learn(
        [snap("1", [{"recipe_id": "a", "liked": True}])],
        liked + choices,
        overrides=swaps,
    )
    picked = pick_meals(choices, taste, set(), set(), {}, 1, swaps)
    assert picked[0]["id"] == 2
    assert "similar to meals you liked" in picked[0]["reasons"]


def test_favorite_spreads_like_a_thumbs_up():
    recipes = [
        meal(1, "Carbonara", ["pasta", "egg"], ["a"]),
        meal(2, "Penne", ["pasta", "tomato"], ["b"]),
        meal(3, "Steak", ["steak", "asparagus"], ["c"]),
    ]
    taste = learn([], recipes)
    picked = pick_meals(recipes, taste, set(), {1}, {}, 3)
    assert [row["id"] for row in picked] == [1, 2, 3]
    assert "favorite" in picked[0]["reasons"]
    assert not taste.from_lab


def test_cooked_favorite_beats_a_thumbs_up():
    recipes = [
        meal(1, "Carbonara", ["pasta", "egg"], ["a"]),
        meal(2, "Roast beef", ["beef"], ["b"]),
    ]
    taste = learn([snap("1", [{"recipe_id": "b", "liked": True}])], recipes)
    picked = pick_meals(recipes, taste, set(), {1}, {}, 2, cooked={1})
    assert [row["id"] for row in picked] == [1, 2]
    assert "you cooked this" in picked[0]["reasons"]
    assert "you liked this" in picked[1]["reasons"]


def test_to_try_beats_a_thumbs_up():
    recipes = [
        meal(1, "Swiped", ["pasta", "tomato"], ["a"]),
        meal(2, "Planned", ["pasta", "tomato"], ["b"]),
    ]
    taste = learn([snap("1", [{"recipe_id": "a", "liked": True}])], recipes)
    picked = pick_meals(recipes, taste, set(), set(), {}, 2, to_try={2})
    assert [row["id"] for row in picked] == [2, 1]
    assert "to try" in picked[0]["reasons"]
    assert "you liked this" in picked[1]["reasons"]


def test_plan_approval_ranks_below_a_thumbs_up():
    recipes = [
        meal(1, "Swiped", ["pasta"], ["a"]),
        meal(2, "Approved", ["beef"], ["b"]),
    ]
    taste = learn(
        [snap("1", [{"recipe_id": "a", "liked": True}], plans=[{"verdict": "up", "recipe_ids": ["b"]}])],
        recipes,
    )
    picked = pick(recipes, taste, want=2)
    assert [row["id"] for row in picked] == [1, 2]
    assert "from a plan you approved" in picked[1]["reasons"]


def test_heart_does_not_stack_on_a_thumbs_up():
    recipes = [meal(1, "Tacos", ["beef"], ["a"])]
    swipes = [snap("1", [{"recipe_id": "a", "liked": True}])]
    both = pick_meals(recipes, learn(swipes, recipes), set(), {1}, {}, 1)[0]["score"]
    only = pick(recipes, learn(swipes, recipes))[0]["score"]
    assert both == only


def test_pass_beats_a_cooked_favorite():
    recipes = [
        meal(1, "Tacos", ["beef"], ["a"]),
        meal(2, "Soup", ["carrot"], ["b"]),
    ]
    taste = learn([snap("1", [{"recipe_id": "a", "liked": False}])], recipes)
    picked = pick_meals(recipes, taste, set(), {1}, {}, 2, cooked={1})
    assert [row["id"] for row in picked] == [2]


def test_household_spicy_avoid_and_time():
    recipes = [
        meal(1, "Hot noodles", ["noodles", "sriracha"], minutes=20),
        meal(2, "Slow stew", ["beef", "potato"], minutes=90),
        meal(3, "Quick stew", ["beef", "potato"], minutes=25),
    ]
    taste = learn([], recipes, avoids=["spicy"], max_minutes=30)
    picked = pick(recipes, taste, want=2)
    assert picked[0]["id"] == 3
    assert 1 not in {row["id"] for row in picked}


def test_reasons_summary_counts_each_meal_once_per_group():
    summary = reasons_summary([
        ["you cooked this", "uses 2 from pantry"],
        ["favorite", "uses 1 from pantry", "to try"],
        ["near a meal you liked"],
        ["another starch, like the pasta you liked"],
        ["3 new grocery items"],
    ])
    assert summary == "1 you've cooked · 3 match your tastes · 1 to try · 2 use your pantry"


def test_reasons_summary_singular_and_empty():
    assert reasons_summary([["you liked this", "uses 1 from pantry"]]) == (
        "1 matches your tastes · 1 uses your pantry")
    assert reasons_summary([["already covered"], []]) == ""


def test_contextual_refusals_accumulate_without_banning():
    from app.domain.taste_rank import suggestion_penalties
    declined = {"decision": "decline", "suggested_recipe_ids": [1], "changes": []}
    assert suggestion_penalties([declined])[1] == 0.75
    assert suggestion_penalties([declined] * 3)[1] == 2.25
    changed = {"decision": "approve", "suggested_recipe_ids": [2], "changes": [{"from": 1, "to": 2}]}
    assert suggestion_penalties([changed])[1] > suggestion_penalties([declined])[1]
    approved = {"decision": "approve", "suggested_recipe_ids": [1], "changes": []}
    assert suggestion_penalties([declined, approved])[1] == 0


def test_public_taste_shows_household_filters_when_given():
    from app.taste_lab import public_taste

    body = public_taste(
        [snap("1", dislikes=["mushrooms"], diets=["vegan"])],
        signed_in=True,
        filters={"diets": ["omnivore"], "allergens": ["sesame"], "avoids": ["olives"], "time": "30"},
    )
    assert body["profile"] == {"diets": ["omnivore"], "allergens": ["sesame"], "dislikes": ["olives"]}


def test_fill_plan_prefers_reusing_selected_meal_ingredients():
    recipes = [
        meal(1, 'Carrot bowl', ['carrot', 'rice']),
        meal(2, 'Pepper bowl', ['bell pepper', 'rice']),
    ]
    taste = learn([], recipes)
    picked = pick_meals(recipes, taste, set(), set(), {}, 1, plan_ings={'bell pepper'})
    assert picked[0]['id'] == 2
    assert 'shares 1 with this plan' in picked[0]['reasons']
