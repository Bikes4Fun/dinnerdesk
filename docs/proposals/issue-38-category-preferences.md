# Category preference proposal — issue #38

Awaiting the user's choice before adding category preferences.

Proposed behavior:

- Dislike stops suggesting a category while leaving its recipes browsable.
- Like boosts the category in suggestions; it does not guarantee a meal on every plan.
- Neutral has no effect. Each category has one state: Like, Neutral, or Dislike.
- Allergies and dietary filters always take priority over category likes.
- If a recipe belongs to several categories, a dislike takes priority over a like.
- Store choices in household preferences, shared by Settings and Taste Lab.
- Do not add a new Recipes carousel until separately requested.

Existing category labels for review: Curry & Indian; Mexican & Tex-Mex; Asian stir-fries &
noodles; Italian & pasta; Mediterranean; Comfort classics; Healthy & light; Soups & stews.

Alternative: disliked categories also disappear from browsing. This makes it harder to find
an occasional exception and needs a clear explanation/reset control before implementing.

Implementation after approval: add persisted tri-state choices, apply the ranker rules,
share controls on app/web, and verify overlapping categories and allergy precedence with tests.
