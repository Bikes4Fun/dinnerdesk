# Dinnerdesk to-do

Open work is on GitHub issues. This file no longer keeps a second copy.

New items go on an issue. When a feature's behavior changes, update [`DESIGN.md`](DESIGN.md) and [`TESTER_CHECKLIST.md`](TESTER_CHECKLIST.md) in the same commit.

| Area | Issue |
|---|---|
| Quick start tour | #24 |
| Accessibility, including the large-text pass | #35 |
| Release checks | #37 |
| Category likes and dislikes | #38 |
| Sample week for guests | #39 |
| More tab nesting | #40 |
| Allergies vs avoids | #81 |
| Ingredient photos | #82 |
| Custom-food search | #85 |
| Cook-mode timers | #87 |
| Planning and suggestions | #88 |
| Recipes and cooking | #89 |
| Grocery, prep, and retailer research | #90 |
| Nutrition and health | #91 |
| People and sharing | #92 |
| Business | #93 |
| Design polish (the old #95 note) | #104 |
| Shared prep components | #116 |
| Cooking education | #117 |
| Suggestion algorithm | #118 |
| Recipe library | #120 |

No issue exists for #84: Taste Lab returning-user spacing is fixed; still reconcile its cards and actions with the earlier simple suggestion layout.

## Even issue implementation record — October 8, 2026

Historical record of the cumulative issue pass. These changes have since been integrated
into `main`; the listed local feature branches were deleted after verifying their ancestry.
The proposals remain unimplemented, and device/browser checks are in the tester checklist.

| Issue | Branch | Result |
|---|---|---|
| #4 | `codex/issue-4-recipe-plan-state` | Actual plan membership; add/remove controls and brief confirmation |
| #6 | `codex/issue-6-remove-dialog` | Singular/plural wording; full-height accessibility confirmation |
| #8 | `codex/issue-8-suggestion-summary` | Review explanation; no internal commentary on active plans |
| #10 | `codex/issue-10-taste-lab-header` | Suppress repeated Taste Lab branding when embedded |
| #12 | `codex/issue-12-taste-lab-names` | Full suggested names and swap headings |
| #14 | `codex/issue-14-taste-lab-recovery` | Prominent exhausted-results recovery panel |
| #16 | `codex/issue-16-recipe-menu` | Shared scrolling iPhone recipe options sheet; device reproduction still needed |
| #18 | `codex/issue-18-grocery-photo` | Omit missing/failed ingredient photo boxes; supplying photos remains an asset task |
| #20 | `codex/issue-20-substitution-layout` | Stack substitution names when space is limited |
| #22 | `codex/issue-22-selected-tab` | Bold selected labels; web underline and aria-current |
| #24 | `codex/issue-24-tour-order` | Tour order proposal is on #24, pending choice |
| #26 | `codex/issue-26-plan-menu` | Remove unrequested chooser menu and unused chooser code |
| #28 | `codex/issue-28-prep-completion` | One PUT endpoint, one JSON store, legacy migration; updated API/app must ship together |
| #30 | `codex/issue-30-plan-list-layout` | Full names and Schedule without shrinking photos |
| #32 | `codex/issue-32-decline-in-place` | Retain review during replacement; failure supports retry |
| #34 | `codex/issue-34-grocery-heading` | Full-width secondary usage heading |
| #36 | `codex/issue-36-tab-reselection` | Same-tab selection returns to root |
| #38 | `codex/issue-38-category-preferences` | Category proposal is on #38, pending choice |
| #40 | `codex/issue-40-more-navigation` | More grouping proposal is on #40, pending choice |

At the time of that pass, 197 Python tests passed in a dedicated database, the unsigned
simulator build and web production build passed, and Taste Lab JavaScript syntax checks
passed. Test isolation resets Taste Lab's cached initializer between fresh schemas.
These are historical results, not validation of the current build. Issue #2's original
HTTP 405 trigger remains unresolved; request diagnostics are in place.

<<<<<<< HEAD
### October 10 TestFlight follow-up

Reports from 1.0.3 (2) are mapped individually in TESTER_CHECKLIST.md. Active fixes: #109 (suggestion lifecycle, fill-in, empty plans), #110 (multiple custom foods, prep Undo, compact Plan, grocery bulk toggle), and #103 (hide staged tips). #85's plural search fix is already merged as PR #98. #82 still needs the prepared ingredient gallery enabled in production. Branch: `fix/testflight-feedback-oct10`.
=======
## Android / Google Play — issue #112

Branch `issue-112-android-google-play` adds the Android app, Gradle wrapper, native navigation/photo picker/grocery sharing/data export, and a release checklist in `android/README.md`. URL policy unit tests passed. Full Android compilation, lint and device testing await Android SDK license acceptance and installation. Play publication also requires the owner's Console app, upload signing key, listing/Data safety declarations, and internal-track acceptance. This is prepared source, not a published Play release.
>>>>>>> e5e4744 (Add Android app and Google Play release preparation for issue 112)
