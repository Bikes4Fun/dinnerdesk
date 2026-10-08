"""Ingredient photos live outside Git; only explicit, recognizable foods are mapped."""
from pathlib import Path
import os
import re
from urllib.parse import quote

# Words that can sit beside a food name without making it a different item.
_MODIFIERS = frozenset(
    """
    small medium large extra fresh raw boneless skinless chopped diced minced
    sliced ground dried dry peeled seeded crushed grated shredded cooked
    uncooked organic frozen thawed stemmed trimmed halved halves half coarsely
    finely roughly thinly thickly packed loose of and with or the a an
    cup cups tbsp teaspoon teaspoons tsp tablespoon tablespoons oz ounce ounces
    lb lbs pound pounds gram grams bunch bunches head heads clove cloves can
    cans package packages bag bags jar jars slice slices piece pieces
    """.split()
)

# Deliberately omit files whose food identity is uncertain.
PHOTOS = {
    'garlic': 'garlic.jpg', 'garlic cloves': 'garlic.jpg',
    'zucchini': 'zuchini of unknown variety.jpg', 'zucchinis': 'zuchini of unknown variety.jpg',
    'anaheim peppers': 'green chili peppers anaheim or hatch style raw.jpg',
    'hatch chiles': 'green chili peppers anaheim or hatch style raw.jpg',
    'carrot': 'orange carrots.jpg', 'carrots': 'orange carrots.jpg',
    'red onion': 'red or purple onions.jpg', 'red onions': 'red or purple onions.jpg',
    'purple onion': 'red or purple onions.jpg', 'purple onions': 'red or purple onions.jpg',
    'onion': 'yellow or sweet onions.jpg', 'onions': 'yellow or sweet onions.jpg',
    'yellow onion': 'yellow or sweet onions.jpg', 'yellow onions': 'yellow or sweet onions.jpg',
    'sweet onion': 'yellow or sweet onions.jpg', 'sweet onions': 'yellow or sweet onions.jpg',
    'shallot': 'shallots.jpg', 'shallots': 'shallots.jpg',
    'red bell pepper': 'red bell pepper.jpg', 'red bell peppers': 'red bell pepper.jpg',
    'yellow bell pepper': 'yellow bell peppers.jpg', 'yellow bell peppers': 'yellow bell peppers.jpg',
    'chicken breast': 'chicken breast.jpg', 'chicken breasts': 'chicken breast.jpg',
    'whole chicken': 'whole chicken.jpg',
    'pinto beans': 'dry pinto beans.jpg', 'dry pinto beans': 'dry pinto beans.jpg',
    'russet potato': 'russet potatos.jpg', 'russet potatoes': 'russet potatos.jpg',
    'red lentils': 'orange or red lentils dry.jpg',
    'brown lentils': 'generic brown or tan dry lentils.jpg',
    'mandarin oranges': 'tangerines cuties or mandarin oranges.jpg',
    'tangerines': 'tangerines cuties or mandarin oranges.jpg',
}


def photo_directory() -> Path | None:
    configured = os.environ.get('GROCERY_PHOTO_DIR')
    if configured is None:
        return None  # No ingredient gallery configured; the UI reserves empty space.
    directory = Path(configured)
    if not configured.strip() or not directory.is_dir():
        raise RuntimeError('GROCERY_PHOTO_DIR must point to an existing ingredient photo directory')
    return directory


def _tokens(name: str) -> list[str]:
    return re.sub(r'[^a-z]+', ' ', name.casefold()).split()


def _filename_for(name: str) -> str | None:
    """Longest food keyword inside the ingredient name. Other words must be modifiers."""
    tokens = _tokens(name)
    if not tokens:
        return None
    for key in sorted(PHOTOS, key=len, reverse=True):
        words = key.split()
        width = len(words)
        for start in range(len(tokens) - width + 1):
            if tokens[start:start + width] != words:
                continue
            leftover = tokens[:start] + tokens[start + width:]
            if all(word in _MODIFIERS for word in leftover):
                return PHOTOS[key]
    return None


def photo_path(name: str) -> str | None:
    directory = photo_directory()
    if directory is None:
        return None
    filename = _filename_for(name)
    if filename is None:
        return None
    path = directory / filename
    if not path.is_file():
        raise RuntimeError(f'Mapped ingredient photo is missing: {filename}')
    return '/grocery-food/' + quote(filename)


def photo_file(filename: str) -> Path | None:
    directory = photo_directory()
    if directory is None or filename not in PHOTOS.values():
        return None
    path = directory / filename
    if not path.is_file():
        raise RuntimeError(f'Mapped ingredient photo is missing: {filename}')
    return path
