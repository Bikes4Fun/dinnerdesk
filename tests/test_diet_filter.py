from app.domain.diet_filter import allowed, blocks_for, normalize_diets


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
