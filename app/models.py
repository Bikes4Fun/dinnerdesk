"""Shared Pydantic payloads."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field


class RecipeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    servings: int = Field(default=4, ge=1, le=50)
    cooking_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    source_url: str = Field(default="", max_length=2000)
    ingredients: list[dict] = Field(default_factory=list)
    instructions: list[dict] = Field(default_factory=list)
    cookware: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    # Read off source_url by POST /recipes/import; the steps came from that site.
    imported: bool = False
    # The user's own photo (a data: URL), or else the imported page's photo to copy. The
    # page's photo link is kept either way as a fallback.
    photo_data: str | None = Field(default=None, max_length=7_000_000)
    photo_url: str = Field(default="", max_length=2000)


class RecipeImport(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


class RecipePatch(BaseModel):
    photo_data: str | None = Field(default=None, max_length=7_000_000)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    servings: int | None = Field(default=None, ge=1, le=50)
    cooking_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    ingredients: list[dict] | None = None
    instructions: list[dict] | None = None
    cookware: list[str] | None = None
    tags: list[str] | None = None
    in_place: bool = True
    as_copy: bool = False


class FavoritePut(BaseModel):
    on: bool


class DevNotesPut(BaseModel):
    text: str = Field(default="", max_length=8000)


class IngredientReviewNotes(BaseModel):
    notes: str = Field(default="", max_length=8000)


class IngredientReviewAnswer(BaseModel):
    action: str = Field(pattern="^(standardize|alias|separate)$")
    target: str = Field(min_length=1, max_length=120)
    names: list[str] = Field(default_factory=list, max_length=100)


class IngredientReviewAudit(BaseModel):
    verdict: str = Field(pattern="^(looks_good|suggested_change|question)$")
    reason: str = Field(min_length=1, max_length=2000)
    suggested_action: str | None = Field(
        default=None,
        pattern="^(standardize|alias|separate)$",
    )
    suggested_target: str = Field(default="", max_length=120)
    suggested_names: list[str] = Field(default_factory=list, max_length=100)


class IngredientReviewAuditResolution(BaseModel):
    resolution: str = Field(
        pattern="^(confirmed|accepted_suggestion|revised|re_review)$"
    )


class HouseholdPut(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    prefs: dict | None = None


class SlotIn(BaseModel):
    id: int | None = None
    recipe_id: int
    day_index: int | None = Field(default=None, ge=0, le=36500)
    meal_type: str = "dinner"
    servings: int | None = Field(default=None, ge=1, le=50)


class SlotsPut(BaseModel):
    slots: list[SlotIn]


class SlotPatch(BaseModel):
    cooked: bool | None = None
    servings: int | None = Field(default=None, ge=1, le=50)
    day_index: int | None = Field(default=None, ge=0, le=36500)
    scheduled_date: date | None = None
    unschedule: bool = False


class GroceryPatch(BaseModel):
    checked: bool | None = None
    quantity: str | None = Field(default=None, max_length=80)
    custom_text: str | None = Field(default=None, max_length=200)
    aisle: str | None = Field(default=None, max_length=40)
    store: str | None = Field(default=None, max_length=40)


class GroceryLineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    quantity: str = Field(default="", max_length=80)
    store: str = Field(default="", max_length=40)
    aisle: str = Field(default="", max_length=40)


class PantryItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    have: bool = True
    never_shop: bool = False
    quantity: str = ""
    zone: str = "dry"


class PantryPut(BaseModel):
    items: list[PantryItemIn]


class PantryPatch(BaseModel):
    have: bool | None = None
    never_shop: bool | None = None
    quantity: str | None = Field(default=None, max_length=40)


class PantryItemUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    have: bool = True
    never_shop: bool = False
    quantity: str | None = Field(default=None, max_length=40)
    zone: str = "dry"


class OverrideIn(BaseModel):
    from_name: str = Field(min_length=1, max_length=120)
    to_name: str = Field(min_length=1, max_length=120)


class OverridesPut(BaseModel):
    items: list[OverrideIn]


class PrepPatch(BaseModel):
    done: bool


class PrepStepPatch(BaseModel):
    """Check off one item (a meal's step) inside a prep task."""
    recipe_id: int
    key: str = Field(min_length=1, max_length=40)
    done: bool


class RatingPut(BaseModel):
    """1 = thumbs up, -1 = thumbs down, 0 = clear."""
    rating: int = Field(ge=-1, le=1)


class PrepStepFeedbackPut(BaseModel):
    recipe_id: int
    key: str = Field(min_length=1, max_length=40)
    text: str = Field(default="", max_length=2000)
    category: str = Field(default="", max_length=120)  # the prep heading it was shown under
    auto: bool = True
    rating: int = Field(ge=-1, le=1)


# Why a prep item isn't worth doing ahead (#21). Logged with the 👎 for review.
PREP_REASONS = ("day_of", "kept_badly", "too_small", "prep_differently", "not_prep")


class PrepTaskFeedbackPut(BaseModel):
    """👍/👎 on a whole prep item (every meal's step in it), with an optional reason and note for a 👎."""
    rating: int = Field(ge=-1, le=1)
    reason: str = Field(default="", pattern="^(|day_of|kept_badly|too_small|prep_differently|not_prep)$")
    note: str = Field(default="", max_length=500)


# Why a cook reports a recipe. Same ids in web/src/pages/Recipe.jsx and ios RecipeReportReason.
RECIPE_REPORT_REASONS = ("ingredients", "steps", "diet", "photo", "duplicate", "turned_out", "other")


class RecipeReportCreate(BaseModel):
    """A cook reporting a problem with a recipe, with a reason and their own words."""
    reason: str = Field(pattern="^(ingredients|steps|diet|photo|duplicate|turned_out|other)$")
    note: str = Field(default="", max_length=1000)


# Bug reports and feature requests (#145). Same ids in web/src/pages/Feedback.jsx and ios FeedbackKind.
FEEDBACK_KINDS = ("bug", "feature")
FEEDBACK_STATUSES = ("new", "planned", "done", "declined")


class FeedbackCreate(BaseModel):
    """A cook reporting a bug or asking for a feature, in their own words."""
    kind: str = Field(pattern="^(bug|feature)$")
    note: str = Field(min_length=1, max_length=2000)
    # Where they were in the app, if the client knows (e.g. "recipes/12").
    screen: str = Field(default="", max_length=200)
    # Up to 3 screenshots as data URLs (JPEG, PNG or WebP, 5 MB each before encoding).
    screenshots: list[Annotated[str, Field(max_length=7_000_000)]] = Field(default_factory=list, max_length=3)


class FeedbackStatusPut(BaseModel):
    status: str = Field(pattern="^(new|planned|done|declined)$")


class PlanReportCreate(BaseModel):
    """A cook reporting a bad meal plan suggestion, in their own words."""
    note: str = Field(default="", max_length=1000)


class PrepMissingPut(BaseModel):
    """A recipe step the household says belongs in Weekend prep but wasn't listed (#21).
    added=False takes the suggestion back."""
    recipe_id: int
    key: str = Field(min_length=1, max_length=40)
    note: str = Field(default="", max_length=500)
    added: bool = True


class SubmissionCreate(BaseModel):
    kind: str = Field(pattern="^(photo|suggestion|review)$")
    body: str = Field(default="", max_length=2000)
    rating: int | None = Field(default=None, ge=1, le=5)
    photo_data: str = Field(default="", max_length=6_000_000)


class PlanCreate(BaseModel):
    title: str = Field(default="This week", min_length=1, max_length=80)
    start_date: date | None = None
    draft: bool = False
    source_plan_id: int | None = None
    meal_count: int | None = Field(default=None, ge=1, le=14)
    keep_current: bool = False


class PlacementPut(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    store: str | None = Field(default=None, max_length=40)
    aisle: str | None = Field(default=None, max_length=40)


class SuggestionResize(BaseModel):
    meal_count: int = Field(ge=1, le=14)


class SuggestionSwap(BaseModel):
    recipe_id: int | None = Field(default=None, gt=0)
