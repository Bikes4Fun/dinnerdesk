from app.domain.diet_filter import allowed, blocks_for, clean_filters, fold_profiles, merge_filters, normalize_diets


def ok(name, ings, diets=(), avoids=()):
    return allowed(name, list(ings), blocks_for(list(diets), list(avoids)))


def test_vegan_hides_meat_fish_dairy_and_eggs():
    assert not ok("Turkey Chili", ["ground turkey", "beans"], diets=["vegan"])
    assert not ok("Salmon Bowl", ["salmon", "rice"], diets=["vegan"])
    assert not ok("Carbonara", ["eggs", "parmesan"], diets=["vegan"])
    assert not ok("Chorizo Hash", ["chorizo", "potatoes"], diets=["vegan"])
    assert ok("Chickpea Curry", ["chickpeas", "coconut milk", "rice"], diets=["vegan"])


def test_plant_based_words_are_not_dairy_or_meat():
    assert ok("Peanut Noodles", ["peanut butter", "rice noodles"], diets=["vegan"])
    assert ok("Squash Soup", ["butternut squash", "coconut cream"], diets=["dairy-free"])
    assert ok("Tacos", ["vegan sausage", "tortillas"], diets=["vegan"])
    assert ok("Eggplant Parm", ["eggplant", "vegan cheese"], diets=["vegan"])


def test_vegetarian_allows_dairy_but_not_fish():
    assert ok("Mac and Cheese", ["pasta", "cheddar", "milk"], diets=["vegetarian"])
    assert not ok("Fish Tacos", ["cod", "tortillas"], diets=["vegetarian"])
    assert not ok("Pad Thai", ["fish sauce", "noodles"], diets=["vegetarian"])


def test_pescatarian_allows_fish_not_meat():
    assert ok("Salmon Bowl", ["salmon"], diets=["pescatarian"])
    assert not ok("Pepperoni Pizza", ["pepperoni"], diets=["pescatarian"])


def test_avoids_and_none():
    assert not ok("Salmon Bowl", ["salmon"], avoids=["fish"])
    assert not ok("Shrimp Scampi", ["shrimp"], avoids=["shellfish"])
    assert not ok("Satay", ["peanuts"], avoids=["peanuts"])
    assert ok("Salmon Bowl", ["salmon"], avoids=["none"])
    assert blocks_for([], ["none"]) == []


def test_no_filters_allows_everything():
    assert ok("Turkey Chili", ["ground turkey"])
    assert ok("Turkey Chili", ["ground turkey"], diets=["omnivore"])


def test_normalize_diets_keeps_one_exclusive_diet():
    assert normalize_diets(["omnivore", "vegetarian", "vegan"]) == ["vegan"]
    assert normalize_diets(["vegan", "omnivore"]) == ["omnivore"]
    assert normalize_diets(["vegetarian", "gluten-free", "dairy-free"]) == [
        "vegetarian", "gluten-free", "dairy-free"]
    assert normalize_diets(["gluten-free", "gluten-free"]) == ["gluten-free"]
    assert normalize_diets([]) == []


# One filter system (#1): Settings → Filters and Taste Lab edit the same household filters.

def test_clean_filters_moves_old_allergy_avoids_and_drops_none():
    out = clean_filters({"diets": ["vegan", "omnivore"], "avoids": ["Peanuts", "shellfish", "none", "olives", "olives"], "time": "30"})
    assert out["diets"] == ["omnivore"]
    assert out["allergens"] == ["peanut", "shellfish"]
    assert out["avoids"] == ["olives"]
    assert out["time"] == "30"
    assert clean_filters(None) == {"diets": ["omnivore"], "allergens": [], "avoids": []}


def test_merge_keeps_what_the_other_screen_set():
    saved = {"diets": ["vegetarian"], "allergens": ["sesame"], "avoids": ["olives"], "time": "45"}
    # The Quick start tour sends diets, avoids and time but not allergies.
    out = merge_filters(saved, {"diets": ["omnivore"], "avoids": [], "time": "30"})
    assert out["allergens"] == ["sesame"]
    assert out["avoids"] == []
    assert out["time"] == "30"
    # Taste Lab sends diets, allergens and avoids but not time.
    out = merge_filters(out, {"diets": ["vegan"], "allergens": [], "avoids": ["kale"]})
    assert out == {"diets": ["vegan"], "allergens": [], "avoids": ["kale"], "time": "30"}


def test_fold_profiles_keeps_every_allergy_and_the_strictest_diet():
    out = fold_profiles(
        {"diets": ["vegetarian", "gluten-free"], "allergens": ["egg"], "avoids": ["spicy"], "time": "any"},
        [
            {"diets": ["vegan"], "allergens": ["sesame"], "dislikes": ["olives", "kale"]},
            {"diets": ["omnivore", "dairy-free"], "allergens": ["egg", "peanuts"], "dislikes": []},
        ],
    )
    assert out["diets"] == ["vegan", "gluten-free", "dairy-free"]
    assert out["allergens"] == ["egg", "sesame", "peanut"]
    assert out["avoids"] == ["spicy", "olives", "kale"]
    assert out["time"] == "any"


def test_allergens_block_meals_like_avoids():
    clean = clean_filters({"allergens": ["tree-nuts", "sesame"]})
    groups = blocks_for(clean["diets"], [*clean["allergens"], *clean["avoids"]])
    assert not allowed("Pesto", ["basil", "pine nuts", "walnuts"], groups)
    assert not allowed("Noodles", ["tahini", "noodles"], groups)
    assert allowed("Tacos", ["beef", "tortillas"], groups)


def test_every_screen_offers_the_same_choices():
    """Settings (web, iOS), the tour and Taste Lab copy these lists; keep them equal."""
    import re
    from pathlib import Path

    from app.domain.diet_filter import ALLERGENS, AVOIDS, DIETS

    root = Path(__file__).resolve().parents[1]

    def quoted(text: str) -> set[str]:
        return set(re.findall(r'"([^"]+)"', text))

    def block(text: str, start: str, end: str) -> str:
        i = text.index(start)
        return text[i:text.index(end, i)]

    web = (root / "web/src/diet.js").read_text()
    assert quoted(block(web, "export const DIETS", ";")) == set(DIETS)
    assert quoted(block(web, "export const ALLERGENS", "];")) & set(ALLERGENS) == set(ALLERGENS)
    assert quoted(block(web, "export const AVOIDS", "];")) == set(AVOIDS)

    lab = (root / "tastelab/web/app.js").read_text()
    assert quoted(block(lab, "const AVOIDS", "];")) == set(AVOIDS)
    assert quoted(block(lab, "const ALLERGENS", "];")) & set(ALLERGENS) == set(ALLERGENS)
    assert quoted(block(lab, "const DIETS", "];")) & set(DIETS) == set(DIETS)

    ios = (root / "ios/dinnerdesk/SettingsView.swift").read_text()
    assert quoted(block(ios, "static let diets", "\n")) == set(DIETS)
    assert quoted(block(ios, "static let allergens", "]\n")) & set(ALLERGENS) == set(ALLERGENS)
    assert quoted(block(ios, "static let avoids", "]\n")) == set(AVOIDS)


def test_specific_food_selection_filters_only_that_ingredient():
    assert not ok("Skillet", ["red bell pepper", "ground turkey"], avoids=["red bell pepper"])
    assert ok("Skillet", ["green bell pepper", "ground turkey"], avoids=["red bell pepper"])
    assert not ok("Chili", ["ground beef", "tomatoes"], avoids=["ground beef"])
    assert ok("Chili", ["ground turkey", "tomatoes"], avoids=["ground beef"])
