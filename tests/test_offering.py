from app.domain.offering import coming_soon, withheld


def test_pizza_breakfast_and_snacks_are_withheld():
    assert withheld("Spinach frittata")
    assert withheld("Grape Tomato Flatbread Pizza with Arugula Salad")
    assert withheld("Pear Nachos with Greek Yogurt")
    assert withheld("Scrambled Tofu Breakfast Burrito")
    assert withheld("Guacamole")
    assert withheld("Pico de gallo")
    assert withheld("Weeknight chili", ["snack"])


def test_dinners_that_mention_a_side_stay_offered():
    assert not withheld("Strip Steak & Bell Pepper Fajitas with Guacamole")
    assert not withheld("Grilled Steak with Mango Salsa & Spinach-Tomato Salad")
    assert not withheld("Bacon Fried Rice with Egg, Brussels Sprouts & Carrots")
    assert not withheld("Baked Honey Mustard Chicken Thighs with Cauliflower & Snap Peas")


def test_a_rewrite_without_a_photo_is_coming_soon():
    data = {"name": "Sheet pan ribs", "instructions_copied_from_third_party": False, "photo_path": ""}
    assert coming_soon(data)
    assert not coming_soon({**data, "photo_path": "food/ribs.jpg"})
    assert not coming_soon({**data, "name": "Spinach frittata"})
    assert not coming_soon({**data, "instructions_copied_from_third_party": True})
