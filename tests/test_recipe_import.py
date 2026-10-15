import json

import pytest

from app.domain import recipe_import
from app.domain.recipe_import import (
    RecipeImportError,
    duration_minutes,
    extract_recipe_ld,
    normalize,
    servings_of,
)


def _page(*nodes) -> str:
    scripts = "".join(
        f'<script type="application/ld+json">{json.dumps(n)}</script>' for n in nodes
    )
    return f"<html><head>{scripts}</head><body>hi</body></html>"


RECIPE = {
    "@type": ["Recipe"],
    "name": "Chicken &amp; Rice",
    "recipeYield": ["4", "4 servings"],
    "prepTime": "PT15M",
    "cookTime": "PT1H",
    "recipeIngredient": ["2 cups white rice", "1 ½ lb chicken thighs", "Salt"],
    "recipeInstructions": [
        {"@type": "HowToSection", "name": "Rice", "itemListElement": [
            {"@type": "HowToStep", "text": "Rinse the <b>rice</b>."},
        ]},
        {"@type": "HowToStep", "text": "Brown the chicken."},
        "Serve.",
    ],
}


def test_finds_recipe_inside_graph():
    page = _page({"@type": "WebSite", "name": "x"}, {"@graph": [{"@type": "Person"}, RECIPE]})
    assert extract_recipe_ld(page)["name"] == "Chicken &amp; Rice"


def test_no_recipe_on_page():
    assert extract_recipe_ld(_page({"@type": "Article"})) is None
    assert extract_recipe_ld("<script type='application/ld+json'>{not json</script>") is None


def test_normalize_shapes_a_draft():
    draft = normalize(RECIPE, "https://example.com/r")
    assert draft["name"] == "Chicken & Rice"
    assert draft["servings"] == 4
    assert draft["cooking_minutes"] == 75
    assert draft["ingredient_lines"][1] == "1 ½ lb chicken thighs"
    assert draft["ingredients"][0] == {"quantity": "2 cups", "name": "white rice"}
    assert draft["ingredients"][2] == {"quantity": "", "name": "Salt"}
    assert [s["text"] for s in draft["instructions"]] == ["Rinse the rice.", "Brown the chicken.", "Serve."]
    assert draft["instructions"][0] == {"text": "Rinse the rice.", "prep": False, "ings": ""}


def test_durations_and_yields():
    assert duration_minutes("PT1H30M") == 90
    assert duration_minutes("P0DT0H45M") == 45
    assert duration_minutes("PT") is None
    assert duration_minutes("") is None
    assert servings_of("Makes 12 cookies") == 12
    assert servings_of(6) == 6
    assert servings_of("200 servings") is None
    assert servings_of(None) is None


@pytest.mark.parametrize("url", ["ftp://example.com/x", "http://127.0.0.1/x", "http://localhost:8000/", "http://10.0.0.5/", "http://169.254.169.254/latest", "not a url"])
def test_refuses_non_public_addresses(url):
    with pytest.raises(RecipeImportError):
        recipe_import._check_url(url)


def test_import_without_recipe_says_so(monkeypatch):
    monkeypatch.setattr(recipe_import, "fetch_page", lambda url: (_page({"@type": "Article"}), url))
    with pytest.raises(RecipeImportError) as caught:
        recipe_import.import_recipe("https://example.com/blog")
    assert caught.value.code == "no_recipe"


def test_image_of_takes_the_first_photo_link():
    from app.domain.recipe_import import image_of

    assert image_of("https://x.com/a.jpg") == "https://x.com/a.jpg"
    assert image_of([{"@type": "ImageObject", "url": "https://x.com/b.jpg"}, "https://x.com/c.jpg"]) == "https://x.com/b.jpg"
    assert image_of(["data:image/png;base64,AAA"]) == ""
    assert image_of(None) == ""
    assert normalize({**RECIPE, "image": "/img/r.jpg"}, "https://example.com/r")["image_url"] == "https://example.com/img/r.jpg"
