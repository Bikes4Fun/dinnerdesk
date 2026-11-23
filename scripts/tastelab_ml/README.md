# Taste Lab ML experiment

Can earlier likes and passes predict which recipes someone will like next?
This offline scaffold follows the load, prepare, and feature steps in the
CS 4320 `balls/main.py` project.

## Prepare swipe examples

Save this synthetic example as `/tmp/tastelab-example.json`.

```json
{
  "recipes": [
    {"id": 1, "ingredients": ["apricot", "chicken"], "tags": ["sweet"]},
    {"id": 2, "ingredients": ["spinach", "lemon"], "tags": ["light and fresh"]}
  ],
  "swipes": [
    {"recipe_id": 1, "liked": true},
    {"recipe_id": 2, "liked": false}
  ]
}
```

From the Dinnerdesk checkout, run:

```sh
python3 scripts/tastelab_ml/main.py /tmp/tastelab-example.json
```

## Refresh and chart the catalog

From the Dinnerdesk checkout, point the refresh command at your local
`dd_support` checkout:

```sh
python3 scripts/tastelab_ml/refresh_snapshot.py \
  /path/to/dd_support/catalog/dinnerdesk/data /tmp/tastelab-catalog.json
python3 scripts/tastelab_ml/charts.py /tmp/tastelab-catalog.json /tmp/tastelab-charts
```

The refresh joins recipes and AI tag proposals by slug, preserves the tag
dimension and source, and records the export time. Ingredients come from
catalog recipe files. The snapshot contains no swipe history.

Open `tags.html` and `ingredients.html` in the output directory. Dot size
shows recipe count. Links get thicker as lift increases. Lift measures how
often a pair appears together relative to how often each item appears on its
own. Focus on a dot to see shared recipe counts and lift.

The tag graph measures associations among recipes with AI tags. The ingredient
graph uses the full snapshot. Links require three shared recipes by default.
Use `--min-shared` to change that threshold. The overview displays up to 120
linked items. **Show staples** reveals seasoning nodes such as salt, black
pepper, and red pepper flakes.

## Future meal-plan handoff

Compare predictions on later swipes against the existing Taste Lab ranking
before adding a preference score to the meal-plan ranker. Diet and allergy
eligibility, plan variety, and ingredient reuse stay in the existing flow.
