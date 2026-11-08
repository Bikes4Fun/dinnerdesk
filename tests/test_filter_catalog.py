import copy
import json
from pathlib import Path

import pytest

from scripts.sync_filter_options import FilterCatalog


@pytest.fixture
def catalog_data():
    path = Path(__file__).resolve().parents[1] / "shared/filter-options.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("change", [
    lambda d: d["diets"].append(d["diets"][0]),
    lambda d: d["times"].append(["15"]),
    lambda d: d["strictest"].append("vegan"),
    lambda d: d["protein_diets"]["vegan"].append("beef-typo"),
])
def test_invalid_shared_definitions_fail_before_generating(catalog_data, change):
    data = copy.deepcopy(catalog_data)
    change(data)
    with pytest.raises(ValueError):
        FilterCatalog(data)


def test_missing_choice_group_is_not_silently_ignored(catalog_data):
    del catalog_data["proteins"]
    with pytest.raises(KeyError):
        FilterCatalog(catalog_data)
