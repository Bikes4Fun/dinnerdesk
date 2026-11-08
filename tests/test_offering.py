from app.domain.offering import withheld


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
