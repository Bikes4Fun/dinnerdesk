from app.domain.grocery import merge_grocery
from app.domain.ingredients import aisle_for, zone_for


def test_black_pepper_is_not_produce():
    assert aisle_for("black pepper") == "pantry"
    assert aisle_for("white pepper") == "pantry"
    assert aisle_for("cayenne pepper") == "pantry"
    assert aisle_for("bell pepper") == "produce"
    assert aisle_for("jalapeño peppers") == "produce"


def test_merge_sums_same_ingredient_across_recipes():
    lines = merge_grocery(
        [
            {"name": "Onion", "quantity": "1", "recipe_id": 1, "recipe_name": "Tacos"},
            {"name": "onion", "quantity": "2", "recipe_id": 2, "recipe_name": "Chili"},
            {"name": "salt", "quantity": "", "recipe_id": 1, "recipe_name": "Tacos"},
        ],
        pantry_have=set(),
        never_shop={"salt"},
        aliases={"cilantro": "cilantro"},
    )
    by_name = {x["name"]: x for x in lines}
    assert by_name["yellow onion"]["quantity"] == "3"
    assert by_name["yellow onion"]["used_by"] == ["Tacos", "Chili"]
    assert by_name["yellow onion"]["used_in"] == [
        {"id": 1, "name": "Tacos", "quantity": "1"},
        {"id": 2, "name": "Chili", "quantity": "2"},
    ]
    assert by_name["salt"]["never_shop"] is True
    assert by_name["salt"]["checked"] is True


def test_merge_applies_alias_and_pantry_flag():
    lines = merge_grocery(
        [
            {
                "name": "coriander leaves",
                "quantity": "1 bunch",
                "recipe_id": 3,
                "recipe_name": "Pico",
            }
        ],
        pantry_have={"cilantro"},
        never_shop=set(),
        aliases={"coriander leaves": "cilantro"},
    )
    assert len(lines) == 1
    assert lines[0]["name"] == "cilantro"
    assert lines[0]["from_pantry"] is True
    assert lines[0]["checked"] is False
    assert lines[0]["aisle"] == "produce"


def test_merge_applies_override_and_collapses_lines():
    lines = merge_grocery(
        [
            {
                "name": "chicken thighs, bone-in skin-on",
                "quantity": "1 lb",
                "recipe_id": 1,
                "recipe_name": "Sheet pan",
            },
            {
                "name": "chicken thighs, boneless skinless",
                "quantity": "2 lb",
                "recipe_id": 2,
                "recipe_name": "Skillet",
            },
        ],
        pantry_have=set(),
        never_shop=set(),
        aliases={},
        overrides={
            "chicken thighs, bone-in skin-on": "chicken thighs, boneless skinless",
        },
    )
    assert len(lines) == 1
    assert lines[0]["name"] == "boneless skinless chicken thighs"
    assert lines[0]["quantity"] == "3 lb"
    assert [m["name"] for m in lines[0]["used_in"]] == ["Sheet pan", "Skillet"]
    assert [m["quantity"] for m in lines[0]["used_in"]] == ["1 lb", "2 lb"]


def test_merge_adds_duplicate_amounts():
    lines = merge_grocery(
        [
            {"name": "chicken breasts, boneless skinless", "quantity": "1 lb", "recipe_id": 1, "recipe_name": "Kebabs"},
            {"name": "chicken breasts, boneless skinless", "quantity": "1 lb", "recipe_id": 2, "recipe_name": "Broccoli"},
        ],
        pantry_have=set(),
        never_shop=set(),
        aliases={},
    )
    assert lines[0]["quantity"] == "2 lb"


def test_merge_sums_three_same_unit_and_keeps_meal_qty():
    lines = merge_grocery(
        [
            {"name": "chicken breast", "quantity": "1 lb", "recipe_id": 1, "recipe_name": "A"},
            {"name": "chicken breast", "quantity": "2 lb", "recipe_id": 2, "recipe_name": "B"},
            {"name": "chicken breast", "quantity": "3 lb", "recipe_id": 3, "recipe_name": "C"},
        ],
        pantry_have=set(),
        never_shop=set(),
        aliases={},
    )
    assert lines[0]["quantity"] == "6 lb"
    assert [m["quantity"] for m in lines[0]["used_in"]] == ["1 lb", "2 lb", "3 lb"]


def test_combine_mixed_units_stays_joined():
    from app.domain.grocery import combine_quantities

    assert combine_quantities(["1 bunch", "1 lb"]) == "1 bunch + 1 lb"
    assert combine_quantities(["½ cup", "1/2 cup"]) == "1 cup"
    assert combine_quantities(["1 lb", "2 lb", "3 lb"]) == "6 lb"
    assert combine_quantities(["1 pound", "2 pounds", "3 pounds"]) == "6 lb"
    assert combine_quantities(["1 pound + 2 pounds + 3 pounds"]) == "6 lb"
    assert combine_quantities(["1 (6 oz) pkg", "1 (6 oz) pkg"]) == "2 (6 oz) pkg"


def test_scale_quantity():
    from fractions import Fraction

    from app.domain.grocery import scale_quantity

    assert scale_quantity("1", Fraction(2, 1)) == "2"
    assert scale_quantity("1 cup", Fraction(1, 2)) == "1/2 cup"
    assert scale_quantity("⅔ cup", Fraction(3, 2)) == "1 cup"


def test_merge_collapses_lime_plurals():
    lines = merge_grocery(
        [
            {"name": "lime", "quantity": "1", "recipe_id": 1, "recipe_name": "Ranch"},
            {"name": "limes", "quantity": "2", "recipe_id": 2, "recipe_name": "Burrito"},
        ],
        pantry_have=set(),
        never_shop=set(),
        aliases={},
    )
    assert len(lines) == 1
    assert lines[0]["name"] == "lime"
    assert lines[0]["quantity"] == "3"


def test_merge_jalapeno_alias():
    lines = merge_grocery(
        [
            {"name": "jalapeño", "quantity": "1", "recipe_id": 1, "recipe_name": "A"},
            {"name": "jalapeño peppers", "quantity": "2", "recipe_id": 2, "recipe_name": "B"},
        ],
        pantry_have=set(),
        never_shop=set(),
        aliases={},
    )
    assert len(lines) == 1
    assert "jalape" in lines[0]["name"]
    assert lines[0]["quantity"] == "3"


def test_merge_collapses_all_purpose_flour_spellings():
    lines = merge_grocery(
        [
            {"name": "all purpose flour", "quantity": "1 cup", "recipe_id": 1, "recipe_name": "A"},
            {"name": "all-purpose flour", "quantity": "1 cup", "recipe_id": 2, "recipe_name": "B"},
        ],
        pantry_have=set(),
        never_shop=set(),
        aliases={},
    )
    assert len(lines) == 1
    assert lines[0]["name"] == "all-purpose flour"
    assert lines[0]["quantity"] == "2 cups"


def test_coerce_repairs_unit_stuck_in_name():
    from app.domain.grocery import coerce_qty_name, split_ingredient_line

    assert split_ingredient_line("1 cup plain Greek yogurt") == ("1 cup", "plain Greek yogurt")
    assert split_ingredient_line("½ cup olives") == ("1/2 cup", "olives")
    assert split_ingredient_line("⅔ cup plain greek yogurt") == ("2/3 cup", "plain greek yogurt")
    assert split_ingredient_line("1½ cups flour") == ("1 1/2 cups", "flour")
    assert split_ingredient_line("1 (4 oz) pkg crumbled feta cheese") == (
        "1 (4 oz) pkg",
        "crumbled feta cheese",
    )
    assert split_ingredient_line("2% milk") == ("", "2% milk")
    assert coerce_qty_name("1", "cup plain greek yogurt") == ("1 cup", "plain greek yogurt")
    assert coerce_qty_name("1", "lb chicken breasts, boneless skinless") == (
        "1 lb",
        "chicken breasts, boneless skinless",
    )
    assert coerce_qty_name("4", "oz feta cheese") == ("4 oz", "feta cheese")
    assert coerce_qty_name("1", "tsp powdered chicken broth") == (
        "1 tsp",
        "powdered chicken broth",
    )
    assert coerce_qty_name("1 lb", "chicken breasts, boneless skinless") == (
        "1 lb",
        "chicken breasts, boneless skinless",
    )
    assert coerce_qty_name("⅔", "cup plain greek yogurt") == ("2/3 cup", "plain greek yogurt")
    assert coerce_qty_name("", "⅔ cup plain greek yogurt") == ("2/3 cup", "plain greek yogurt")


def test_merge_repairs_kebab_style_overlay_and_merges_chicken():
    lines = merge_grocery(
        [
            {
                "name": "cup plain greek yogurt",
                "quantity": "1",
                "recipe_id": 2599,
                "recipe_name": "Chicken Kebabs",
            },
            {
                "name": "oz feta cheese",
                "quantity": "4",
                "recipe_id": 2599,
                "recipe_name": "Chicken Kebabs",
            },
            {
                "name": "lb chicken breasts, boneless skinless",
                "quantity": "1",
                "recipe_id": 2599,
                "recipe_name": "Chicken Kebabs",
            },
            {
                "name": "tsp powdered chicken broth",
                "quantity": "1",
                "recipe_id": 2599,
                "recipe_name": "Chicken Kebabs",
            },
            {
                "name": "boneless skinless chicken breasts",
                "quantity": "1 lb",
                "recipe_id": 12,
                "recipe_name": "Cheesy Cheddar Broccoli & Chicken",
            },
        ],
        pantry_have=set(),
        never_shop=set(),
        aliases={},
    )
    by_name = {x["name"]: x for x in lines}
    assert "cup plain greek yogurt" not in by_name
    assert by_name["plain greek yogurt"]["quantity"] == "1 cup"
    assert by_name["feta cheese"]["quantity"] == "4 oz"
    assert by_name["powdered chicken broth"]["aisle"] == "pantry"
    assert by_name["boneless skinless chicken breasts"]["aisle"] == "meat"
    assert by_name["boneless skinless chicken breasts"]["quantity"] == "2 lb"
    assert by_name["boneless skinless chicken breasts"]["used_by"] == [
        "Chicken Kebabs",
        "Cheesy Cheddar Broccoli & Chicken",
    ]
