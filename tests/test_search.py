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


# #85: custom allergy/avoid food search.

def test_custom_food_search_handles_plurals_accents_and_compounds():
    from app.domain.search import filter_item_matches
    names = ["bell pepper", "red bell pepper", "tomato", "cherry tomatoes", "strawberry", "blueberries",
             "jalapeño", "jalapeno pepper", "ground beef", "onion", "green onions", "shrimp"]
    assert filter_item_matches(names, "tomatoes")[:2] == ["tomato", "cherry tomatoes"]
    assert filter_item_matches(names, "strawberries") == ["strawberry"]
    assert "blueberries" in filter_item_matches(names, "berries")
    assert filter_item_matches(names, "Jalapeño") == ["jalapeño", "jalapeno pepper"]
    assert filter_item_matches(names, "jalapeno") == ["jalapeño", "jalapeno pepper"]
    assert filter_item_matches(names, "bell peppers")[0] == "bell pepper"
    assert filter_item_matches(names, "onions") == ["onion", "green onions"]
    assert filter_item_matches(names, "ground")[0] == "ground beef"
    assert filter_item_matches(names, "pep")[0] == "bell pepper"
    # Never invents a food, and every word has to match.
    assert filter_item_matches(names, "kale") == []
    assert filter_item_matches(names, "red onion") == []
    assert filter_item_matches(names, "  ") == []


def test_custom_food_search_finds_typos_without_dropping_query_words():
    from app.domain.search import filter_item_matches

    names = ["cremini mushroom", "sandwich", "cheddar", "mushroom", "red onion"]
    assert filter_item_matches(names, "crimini") == ["cremini mushroom"]
    assert filter_item_matches(names, "sandwhich") == ["sandwich"]
    assert filter_item_matches(names, "chedar") == ["cheddar"]
    assert filter_item_matches(names, "cheddarx") == ["cheddar"]
    assert filter_item_matches(names, "cheddra") == ["cheddar"]
    assert filter_item_matches(names, "mushroms") == ["mushroom", "cremini mushroom"]
    assert filter_item_matches(names, "crimini mushrrom") == ["cremini mushroom"]
    assert filter_item_matches(names, "crimini onion") == []
    assert filter_item_matches(names, "crimini", limit=0) == []


def test_custom_food_search_keeps_literal_matches_first_and_short_words_strict():
    from app.domain.search import filter_item_matches

    assert filter_item_matches(["rice", "rice noodles", "ryce"], "rice") == [
        "rice", "rice noodles", "ryce",
    ]
    assert filter_item_matches(["yam", "ham", "egg", "fig"], "ham") == ["ham"]
    assert filter_item_matches(["onion", "pepper"], "zzzzzz") == []
    assert filter_item_matches(["chicken", "coconut"], "choclate") == []


def test_grocery_search_finds_typos_after_literal_matches():
    names = ["white mushroom", "cremini mushroom", "sandwich", "crimini seasoning"]
    hits, _ = search_grocery_names(names, "crimini")
    assert hits[:2] == ["crimini seasoning", "cremini mushroom"]
    hits, _ = search_grocery_names(names, "sandwhich")
    assert hits[0] == "sandwich"
    hits, _ = search_grocery_names(["jalapeño pepper", "salt"], "jalapeno")
    assert hits[0] == "jalapeño pepper"
