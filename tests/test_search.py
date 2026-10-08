from app.domain.search import recipe_matches, search_grocery_names


def test_protein_swap_still_matches_dish():
    assert recipe_matches(
        "beef bolognese",
        "Spaghetti with Turkey Bolognese",
    )
    assert recipe_matches(
        "beef bolognese",
        "Lentil-Walnut Bolognese Fettuccine with Artichoke Mixed Greens",
    )


def test_literal_phrase_not_required():
    assert not recipe_matches("beef bolognese", "Grilled Chicken Avocado Salad")


def test_protein_only_still_filters():
    assert recipe_matches("turkey", "Spaghetti with Turkey Bolognese")
    assert not recipe_matches("turkey", "Pasta Bolognese")


def test_ground_turk_finds_turkey():
    names = [
        "soy sauce",
        "coconut aminos",
        "ground turkey",
        "ground beef",
        "turkey breast",
        "yellow onion",
    ]
    hits, note = search_grocery_names(names, "ground turk", limit=8)
    assert hits[0] == "ground turkey"
    assert "ground beef" in hits
    assert note in ("", "closest")


def test_grocery_search_never_empty():
    names = ["salt", "onion", "garlic"]
    hits, note = search_grocery_names(names, "zzzz-not-a-food", limit=3)
    assert hits == names
    assert note == "ideas"


def test_grocery_search_prefers_the_item_itself():
    names = ["sugar snap peas", "brown sugar", "powdered sugar", "sugar"]
    hits, _ = search_grocery_names(names, "Sugar", limit=4)
    assert hits[0] == "sugar"
    assert hits.index("brown sugar") < hits.index("sugar snap peas")
    hits, _ = search_grocery_names(["sugar snap peas", "brown sugar"], "sugar", limit=2)
    assert hits[0] == "brown sugar"
