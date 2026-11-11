# Prep feedback review — November 8, 2026

Source: `inbox-prep-open-2026-11-08.json`, 14 feedback records. Account and household
data are intentionally omitted from these examples and regression tests.

The current implementation uses semantic rules. It does not train or claim to
learn automatically. Preserve recipe wording, step keys, and household feedback
separately from generated display wording so future learning can use the original
input and reviewed decisions without treating generated edits as user labels.

| Recipe | Reviewed decision |
| --- | --- |
| 14 | Keep vegetable chopping and dressing preparation; exclude salad assembly. |
| 57 | Garlic is the object of peeling/mincing; bok choy after “set half aside for” is a destination. Bok choy has its own rinse/trim job. This addresses both households' duplicate reports. |
| 57 | Resolve “the other half” only after an explicit split with one ingredient. Show half the quantity when it can be parsed. Preserve unresolved wording when evidence is insufficient. |
| 57 | Include draining/cubing tofu. Do not invent a marinade or modify the recipe based on a tentative question. |
| 379 | Show available recipe amounts beside each instruction, including mayonnaise/mayo and distinct spice powders. |
| 16 | Exclude automatic chicken cutting/seasoning and meat marination pending a system that schedules prep by date. |
| 138 | Keep the dressing instruction and show ingredient amounts and storage guidance. |
| 15 | Include the explicit beet-roasting instruction. |
| 51 | Include quinoa cooking and contiguous simmer/cover/fluff instructions, ending at another cooking task. Exclude chicken basting. |
| 244 | Keep herb stripping/mincing with rinsing and show storage instructions. The record marked “unsure the issue; review later” remains unresolved; no speculative recipe change. |

Explicit recipe prep tags and household additions retain precedence over automatic
selection. Storage guidance appears separately from recipe wording. Cooked food
guidance follows [FoodSafety.gov](https://www.foodsafety.gov/keep-food-safe/4-steps-to-food-safety).
For arbitrary raw sauces, herbs and cut produce, the algorithm supplies container,
refrigeration and separation guidance without inventing a universal shelf life.

Manual review: recipe 57 garlic/bok choy and glaze amounts; recipe 379 mixture
amounts; recipes 14/138 separate dressing and salad; recipes 15/51 cooked prep;
recipe 244 herbs; shared tasks across meals; persisted completion and feedback.
