import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.report_options import ReportCatalog
from app.models import IngredientReportCreate, PrepTaskFeedbackPut, RecipeReportCreate
from scripts.sync_report_options import ReportCatalog as Generator

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def catalog_data():
    return json.loads((ROOT / "shared/report-options.json").read_text(encoding="utf-8"))


def test_all_report_models_and_clients_match_the_catalog(catalog_data):
    generator = Generator(catalog_data)
    for kind, rows in catalog_data.items():
        assert ReportCatalog.choices(kind) == tuple(map(tuple, rows))
        assert ReportCatalog.labels(kind) == dict(rows)
    for path, expected in generator.outputs(ROOT).items():
        assert path.read_text(encoding="utf-8") == expected, f"Regenerate {path.relative_to(ROOT)}"


@pytest.mark.parametrize("kind, model, extra", [
    ("recipe", RecipeReportCreate, {}),
    ("ingredient", IngredientReportCreate, {}),
    ("prep", PrepTaskFeedbackPut, {"rating": -1}),
])
def test_every_client_reason_is_accepted_and_unknown_reasons_are_rejected(kind, model, extra):
    for reason in ReportCatalog.ids(kind):
        value = model(reason=reason, note="Keep the original details", **extra)
        assert value.reason == reason
        assert value.note == "Keep the original details"
    for invalid in ("unknown", "photo_extra", "missing", "PHOTO"):
        with pytest.raises(ValidationError):
            model(reason=invalid, **extra)


def test_prep_reason_remains_optional_for_a_simple_vote():
    assert PrepTaskFeedbackPut(rating=1).reason == ""
    assert PrepTaskFeedbackPut(rating=-1, reason="").reason == ""


@pytest.mark.parametrize("kind, model, limit, extra", [
    ("recipe", RecipeReportCreate, 1000, {}),
    ("ingredient", IngredientReportCreate, 1000, {}),
    ("prep", PrepTaskFeedbackPut, 500, {"rating": -1}),
])
def test_existing_note_limits_are_preserved(kind, model, limit, extra):
    reason = ReportCatalog.ids(kind)[0]
    assert len(model(reason=reason, note="x" * limit, **extra).note) == limit
    with pytest.raises(ValidationError):
        model(reason=reason, note="x" * (limit + 1), **extra)


@pytest.mark.parametrize("change", [
    lambda data: data["prep"].append(data["prep"][0]),
    lambda data: data["recipe"].append(["bad|pattern", "Bad id"]),
    lambda data: data["ingredient"].append(["new_reason", ""]),
    lambda data: data.pop("prep"),
])
def test_invalid_definitions_fail_before_generating(catalog_data, change):
    data = copy.deepcopy(catalog_data)
    change(data)
    with pytest.raises(ValueError):
        Generator(data)


def test_admin_uses_the_same_labels_and_keeps_missing_step_label_separate():
    from app.admin_routes import PREP_REASONS

    assert PREP_REASONS == {**ReportCatalog.labels("prep"), "missing": "Missing prep step"}
