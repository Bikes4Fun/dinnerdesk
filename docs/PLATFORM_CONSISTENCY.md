# Platform consistency (#288)

Web, iPhone and Android use one household API and must offer the same user actions.
Platform UI conventions may differ. Administration is intentionally web-only; native apps
may link to it, but must not reimplement its permissions or workflows.

This is a source audit, not a claim that every action has passed device testing. A screen
or API method existing does not prove that all of its controls work or have matching behavior.

## Ownership and reuse

| System | Shared authority | Platform adapter |
|---|---|---|
| Authentication, household permissions | `app/auth.py`, `app/auth_routes.py` | Web `api.js`; iOS `AuthAPI.swift`; Android `Session.kt` |
| Plan, groceries, recipes, prep, ranking | `app/routes.py`, `app/domain/`, `app/db/` | Web `api.js`/`week.jsx`; iOS `Store.swift`; Android `data/Store.kt` |
| Filter choices and diet-specific protein choices | `shared/filter-options.json` | Generated native filter models and web definitions |
| User-facing shared wording | `ios/dinnerdesk/copy.json` | Native Copy adapters and web `Copy` class; tour descriptions read the same keys |
| HTTP errors, session state, cache | API contract; semantics must agree | Each platform's API/cache/session services |
| Photos, thumbs, ingredient quantities, step formatting | Recipe API and domain rules | Reusable photo, thumbs, quantity and step components per platform |
| Administration | Server admin authorization | Web admin pages only |

Prefer classes, value types, enums and reusable components with clear responsibilities.
Keep business decisions out of individual screens. Pure domain functions and React hooks
are valid reusable abstractions; wrapping each function in a class does not create parity.
Cross-platform reuse means sharing data/contracts, not trying to run SwiftUI in a browser.

## Feature coverage to verify

| Feature | Web source | iOS source | Android source | Audit status |
|---|---|---|---|---|
| Sign in, guest kitchen, password reset | Auth pages | `AuthView.swift`, `AuthAPI.swift` | `AuthView.kt`, `Session.kt` | Implementations present; device flows need comparison |
| Quick start and saved filters | `Tour.jsx`, Settings | `TourView.swift`, Settings | `TourView.kt`, Settings | Shared definitions and tour descriptions; device checks remain |
| Suggestions, swaps, approval | Plan/Suggest pages | `PlanView.swift`, Store | `PlanView.kt`, Store | Implementations present; compare counts, cancellation and refresh |
| Scheduling, cooked meals, drafts/history | Plan pages | `PlanView.swift` | `PlanView.kt` | Implementations present; compare bulk operations |
| Recipe search, favorites, To try, hidden recipes | Recipes/Recipe pages | `RecipesView.swift` | `RecipesView.kt` | Implementations present; compare all list and detail actions |
| Own recipes, import, edit, restore/copy | MyRecipes/Recipe | `MyRecipesView.swift`, Recipes | `MyRecipesView.kt`, Recipes | Implementations present; compare editing and ownership boundaries |
| Recipe photo gallery and uploads | `RecipeGallery.jsx` | Recipes gallery | Recipes gallery | Compare primary/delete/upload and failure handling |
| Recipe, grocery and prep reports | Recipe/Grocery/Prep | Model enums and views | Model enums, Store and views | IDs/labels duplicated; consolidation pending |
| Shopping, store/aisle, custom lines | Grocery/Stores | Grocery/GroceryStore | Grocery/GroceryStore | Implementations present; compare edits, ordering and persistence |
| Pantry, staples, substitutions, kitchen | Kitchen/Pantry pages | Kitchen/Pantry | Kitchen views and KitchenApi | Implementations present; compare all actions |
| Prep check-offs, votes, missing steps | Prep page | `PrepView.swift` | `PrepView.kt` | Another session owns #116 changes; coordinate before editing |
| Taste Lab swipes, history, plans | `tastelab/web/` | `TasteLabView.swift` | Embedded Taste Lab in Settings | Delivery differs; native Android Taste Lab is not required for parity |
| Account data export, deletion, household members | Settings | Settings | Settings | Implementations present; compare roles and confirmations |
| Offline cache and pending changes | API/week/page state | ResponseCache/Store | ResponseCache/PendingWrites/Store | Different implementations; behavior audit pending |
| Timers | Disabled inline timers | Disabled inline timers | Inspect recipe controls | Intentionally disabled behavior must remain consistent |
| Admin inbox and catalog tools | `app/admin_pages/` | Web link only | Web link only | Intentional web-only exception |
| Apple Watch companion | Not applicable | Watch target | Not applicable | Intentional device-specific surface |

## Completion tracking

- [x] Establish shared-system ownership and source inventory.
- [x] Centralize filter definitions; include Android in drift checks.
- [x] Match diet-specific protein selection on all clients.
- [ ] Consolidate shared copy and report choices.
- [ ] Audit every user action, including empty, error and offline states.
- [ ] Close remaining confirmed gaps with focused tests.
- [ ] Complete web, iOS and Android device verification.

Do not mark #288 complete until the remaining checks are addressed. Keep each completed
system as a reviewable commit/PR and keep other sessions' work separate.
