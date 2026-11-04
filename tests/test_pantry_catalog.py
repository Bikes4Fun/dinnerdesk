from app.domain.pantry_catalog import (
    catalog_entries,
    collapse_catalog_names,
    preferred_grocery_name,
)


def test_preferred_merges_plurals_and_hyphens():
    assert preferred_grocery_name("limes") == preferred_grocery_name("lime")
    assert preferred_grocery_name("lime") == "lime"
    assert preferred_grocery_name("all purpose flour") == "all-purpose flour"
    assert preferred_grocery_name("all-purpose flour") == "all-purpose flour"
    assert preferred_grocery_name("bread flour") == "bread flour"
    assert preferred_grocery_name("3/4 pound lean ground beef") == preferred_grocery_name(
        "lean ground beef"
    )
    assert "pound" not in preferred_grocery_name("3/4 pound lean ground beef")
    assert preferred_grocery_name("1 cup 2% milk") == "2% milk"
    assert preferred_grocery_name("1/4 cup grated parmesan cheese") == "grated parmesan cheese"
    assert preferred_grocery_name("2% milk") == "2% milk"
    assert preferred_grocery_name("jalapeño") == preferred_grocery_name("jalapeño pepper")
    assert preferred_grocery_name("fresh mozzarella cheese") == "mozzarella cheese"
    assert preferred_grocery_name("yukon gold potatoes") == "yellow potatoes"
    assert preferred_grocery_name("<!DOCTYPE html>") == ""


def test_collapse_keeps_one_sweet_potato_and_distinct_colors():
    names = collapse_catalog_names(
        [
            "sweet potato",
            "sweet potatoes",
            "yellow potatoes",
            "russet potatoes",
            "red potatoes",
            "all purpose flour",
            "all-purpose flour",
        ]
    )
    assert names.count("sweet potatoes") == 1
    assert "sweet potato" not in names
    assert "yellow potatoes" in names
    assert "russet potatoes" in names
    assert "red potatoes" in names
    flour = [n for n in names if "flour" in n and "almond" not in n and "bread" not in n]
    assert len(flour) == 1
    assert flour[0] == "all-purpose flour"


def test_catalog_entries_add_missing_staples():
    items = catalog_entries(
        [{"name": "yellow potatoes"}, {"name": "sweet potato"}],
        [],
    )
    names = [name for name, _zone in items]
    assert "russet potatoes" in names
    assert "white potatoes" in names
    assert "bread flour" in names
    assert names.count("sweet potatoes") == 1
    assert "sweet potato" not in names


def test_filter_search_collapses_plural_duplicates_and_keeps_food_varieties():
    from app.domain.search import filter_item_matches

    names = collapse_catalog_names([
        "red bell pepper", "red bell peppers", "green bell pepper", "yellow bell pepper",
        "black pepper", "red pepper flakes",
    ])
    hits = filter_item_matches(names, "bell pepper")
    assert len(hits) == 3
    assert sum("red bell" in name for name in hits) == 1
    assert any("green bell" in name for name in hits)
    assert any("yellow bell" in name for name in hits)
    assert "black pepper" in names
    assert "red pepper flakes" in names


def test_ingredient_identity_is_shared_for_aliases_and_private_names():
    from app.domain.pantry_catalog import ingredient_name
    assert ingredient_name("  GREEN   ONION ") == ingredient_name("green onions")
    assert ingredient_name("  FAMILY   SECRET MIX ") == "family secret mix"
    assert ingredient_name("LiMeS") == ingredient_name("lime")
