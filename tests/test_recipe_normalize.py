"""Recipe normalization: one shape for every catalog recipe, done on the recipe itself."""
from app.domain.grocery import coerce_qty_name
from app.domain.recipe_normalize import normalize_recipe


def _myplate():
    return {
        "ingredients": [
            {"quantity": None, "name": "4 medium chicken breasts, boneless & skinless"},
            {"quantity": None, "name": "1 teaspoon cumin"},
            {"quantity": None, "name": "5 tablespoons apricot spread", "note": "about 1/3 cup"},
            {"quantity": None, "name": "2 tablespoons water"},
        ],
        "instructions": [
            {"step": "Wash hands with soap and water.", "ingredients_for_step": None},
            {"step": "Rub cumin over chicken and place in skillet.", "ingredients_for_step": None},
            {"step": "Add apricot spread and water to skillet.", "ingredients_for_step": None},
            {"step": "Spoon sauce over chicken and serve warm.", "ingredients_for_step": None},
        ],
    }


def test_amounts_split_with_the_grocery_parser():
    out, _ = normalize_recipe(_myplate())
    assert out["ingredients"][1] == {"quantity": "1 teaspoon", "name": "cumin"}
    assert out["ingredients"][2]["note"] == "about 1/3 cup"


def test_ranges_and_pinches():
    assert coerce_qty_name("", "5 to 8 garlic cloves, sliced") == ("5 to 8", "garlic cloves, sliced")
    assert coerce_qty_name("", "2-3 tablespoons oil") == ("2-3 tablespoons", "oil")
    assert coerce_qty_name("", "Pinch salt") == ("Pinch", "salt")
    assert coerce_qty_name("", "2% milk") == ("", "2% milk")


def test_each_ingredient_on_the_first_step_that_uses_it():
    steps = normalize_recipe(_myplate())[0]["instructions"]
    assert [s["ingredients_for_step"] for s in steps] == [
        None,  # hand washing isn't the recipe's water
        "4 medium chicken breasts, boneless & skinless\n1 teaspoon cumin",
        "5 tablespoons apricot spread\n2 tablespoons water",
        None,  # the chicken was already counted
    ]


def test_closest_match_wins():
    recipe = {
        "ingredients": [{"quantity": "2 tsp", "name": "olive oil"}, {"quantity": "2 tsp", "name": "pecan oil"}],
        "instructions": [{"step": "Drizzle with olive oil."}, {"step": "Toss with pecan oil."}],
    }
    steps = normalize_recipe(recipe)[0]["instructions"]
    assert [s.get("ingredients_for_step") for s in steps] == ["2 tsp olive oil", "2 tsp pecan oil"]


def test_recipes_already_in_shape_are_untouched():
    recipe = {
        "ingredients": [{"quantity": "1 cup", "name": "rice"}, {"quantity": "2 cups", "name": "water"}],
        "instructions": [{"step": "Rinse the rice.", "ingredients_for_step": "1 cup rice"},
                         {"step": "Serve.", "ingredients_for_step": ""}],
    }
    out, notes = normalize_recipe(recipe)
    assert out is recipe and notes == []
    once = normalize_recipe(_myplate())[0]
    assert normalize_recipe(once) == (once, [])
