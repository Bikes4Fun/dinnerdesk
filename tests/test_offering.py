from app.domain.offering import Offering


def test_pizza_breakfast_and_snacks_are_withheld():
    assert Offering.withheld("Spinach frittata")
    assert Offering.withheld("Grape Tomato Flatbread Pizza with Arugula Salad")
    assert Offering.withheld("Pear Nachos with Greek Yogurt")
    assert Offering.withheld("Scrambled Tofu Breakfast Burrito")
    assert Offering.withheld("Guacamole")
    assert Offering.withheld("Pico de gallo")
    assert Offering.withheld("Weeknight chili", ["snack"])


def test_dinners_that_mention_a_side_stay_offered():
    assert not Offering.withheld("Strip Steak & Bell Pepper Fajitas with Guacamole")
    assert not Offering.withheld("Grilled Steak with Mango Salsa & Spinach-Tomato Salad")
    assert not Offering.withheld("Bacon Fried Rice with Egg, Brussels Sprouts & Carrots")
    assert not Offering.withheld("Baked Honey Mustard Chicken Thighs with Cauliflower & Snap Peas")
