from app.domain.categories import categorize, labels, main_dish


def test_name_puts_recipe_in_its_cuisine():
    assert categorize("Ground Turkey & Chickpea Curry with Basmati Rice") == ["curry"]
    assert categorize("Spaghetti with Turkey Bolognese") == ["italian"]
    assert categorize("Chicken Kebabs with Greek Salad & Tzatziki Sauce") == ["mediterranean"]
    assert categorize("Sesame Chicken & Broccoli with Basmati Rice") == ["asian"]
    assert categorize("Pulled pork") == ["comfort"]


def test_sides_do_not_decide_the_category():
    assert main_dish("Pork Chops with Blackberry Sauce & Lemon Arugula Salad") == "pork chops"
    assert "healthy" not in categorize("Pork Chops with Blackberry Sauce & Lemon Arugula Salad")
    assert categorize("Cauliflower & Chickpea Coconut Curry with Couscous") == ["curry"]


def test_a_recipe_can_be_in_two_categories():
    assert categorize("Curried Coconut Pumpkin Soup with Chicken & Crusty Bread") == ["curry", "soups"]
    assert set(categorize("Chinese Chicken Salad with Napa Cabbage")) == {"asian", "healthy"}


def test_strong_ingredients_alone_need_two_signs():
    assert "mexican" in categorize("Weeknight Dinner", ["flour tortillas", "salsa", "black beans"])
    assert categorize("Weeknight Dinner", ["flour tortillas", "black beans"]) == []
    # One common ingredient isn't enough to call a dish Asian.
    assert "asian" not in categorize("Glazed Salmon", ["salmon", "soy sauce", "honey"])


def test_word_parts_do_not_match():
    # "dal" is lentils; it must not match inside other words.
    assert "curry" not in categorize("Scandal Sandwich")
    assert "italian" not in categorize("Pastrami Melt")


def test_labels_are_readable():
    assert labels(["curry", "soups", "nope"]) == ["Curry & Indian", "Soups & stews"]
