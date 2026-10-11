# Dinnerdesk tester checklist

*Updated Oct 9, 2026 · Branch: `merge_all_issues` · Odd-issue PRs #51–57 integrated; 209 tests and iPhone/web builds pass. Record the app/server version you actually test.*

**Daily: do only the five checks below (about 10 minutes).** Use one platform; alternate iPhone and website. After a relevant change, pick its extra checks. Before a release, cover both platforms. You do not need to repeat the whole checklist every day.

## Daily essentials

- [ ] **Cook opens promptly:** open a recipe, switch Overview → Cook → Overview. Steps and amounts remain readable; no freeze, crash, or timer buttons.
- [ ] **Plan controls work:** add a recipe, then remove it. Toolbar/bottom controls agree, confirmation appears, and there is no duplicate meal.
- [ ] **Suggestions preserve your plan:** request four meals and swap one. The current plan/groceries stay unchanged until approval. Approve and confirm the reviewed meals become the plan.
- [ ] **Groceries match the plan:** amounts combine for shared ingredients. Removing one meal preserves ingredients still needed by another. Check an item and refresh; its check persists.
- [ ] Filters still apply: inspect the suggested meals against your saved diet/allergies/avoids. Reopen the app/page and confirm the plan remains saved.

## Recent changes — pick only what changed

| Area | Quick check |
|---|---|
| **Suggestion layout** | **Restart with saved suggestions: Plan opens, not the review sheet.** Tap **Review saved suggestions** to resume. **Photos are square everywhere:** check suggestion review, plan list/grid, recipes/detail, groceries/detail, and Taste Lab (intro/swipe/plans/swap) at narrow and wide widths. Missing photos use square placeholders; unavailable ingredient photos disappear. Swap picker uses cream styling and searchable, full names; empty results link to Filters. Empty-plan actions sit together. Check four meals at normal text and reachable actions at large text. |
| **Decline / retry** | Decline replaces only the proposal. A failed replacement offers **Try another suggestion**; a declined plan cannot be approved or edited. |
| **Recipe detail** | ⋯ stays open and all options are reachable. Favorite, To try, Hide/Unhide, servings, Edit/Restore, and instruction attribution work. Search uses the cream palette. AI-tagged photos show the purple-star attribution tip. |
| **Taste Lab** | **Try both entry buttons:** Swipe meals skips the quiz and ends without forcing plans; Suggest plans works without swiping. Intro photos/heading/buttons have breathing room; scroll if needed at large text. Edit filters in either mode. Like/pass, swap/More options and reject work; answers do not repeat. Three plan approvals finish; **Done for now** ends early. Empty results offer recovery. |
| **Plan / drafts** | **iPhone 16, normal text:** four meals, full names, Schedule controls, and Add meals should fit without scrolling in the main list. Photos stay square; larger text can scroll. **Edit:** checkbox sits on the right; Schedule/votes and servings use two rows when they fit, stacking at large text. Select/remove, change portions, vote and Done work. Full names, cooked/undo and removal confirmation remain readable. Save/load/delete a draft; active plan is protected. |
| **Filters** | Pantry search supports clear, keyboard arrows, and Return. Filter search: “bell peppers”, “ground”, “tomatoes”, “strawberries”, “jalapeno”; matches appear as **+ chips**; tap one, see **Saving… → ✓ Saved**, reopen, then remove it. Unknown searches show no unrelated results. **None** clears selections. |
| **Grocery / kitchen** | **Set Family portions to 8:** an unplanned recipe shows 8, adding it scales groceries, and new suggestions use 8. Existing meals keep their portions; an explicit recipe choice wins. Missing photos leave no empty box. Substitution, pantry, stores/aisles and completed-item controls persist. |
| **Weekend prep** | Items sit in food sections (Vegetables, Aromatics…, Protein, Sauces), one row per item even when several meals share it. Collapse and reopen a section with its arrow. Check an item: it leaves the list, the ring and its section bar move, and a bar offers Undo and 👍/👎 (👎 shows reasons). **Show completed** brings done items back faded. Closed rows show no thumbs or days; open one (name or chevron) for 👍/👎 (👎 asks why), each step with its cook day on the left, and a purple recipe pill that opens the recipe. At the bottom, **Missing a prep step?**: pick a meal, a step, add a note, Add to prep; it appears as "Added by you", and Remove from prep in the same sheet takes it out. Refresh: check-offs, votes and added steps stay. |
| **Navigation / account** | **Grocery → garlic → Plan → Grocery returns to the grocery list.** Repeat with Recipe detail and More → Settings; reselecting the active tab also returns home. Saved data stays intact. Tour pictures appear below their text; selected-tab styling stays within the bar. Household name saves and reset email sends only when tapped. |

## Before a release — not daily

- [ ] **Accessibility:** smaller phone, largest text, narrow web window, and VoiceOver. Check recipe, suggestion, Grocery, and Prep screens; no clipped names, overlap, or unreachable decisions.
- [ ] **Account access:** sign-up/sign-in/out, password reset, invite/join/remove a household member. Removed members lose access; shared data matches across app and web.
- [ ] **Delete account (#65):** Account & security → Delete account asks for the password; a wrong one is refused. An invited member deleting leaves the household for the owner; the last member deleting removes the household, and the email can sign up again.
- [ ] **Recovery and persistence:** failed requests show readable retry guidance, including missing or unsupported API routes; pending proposals and saved edits survive restart. Verify search, share/print, and tour skip/replay.
- [ ] **Deployment:** updated API/app ship together, prep completion migration is verified, and catalog/photo paths work. Startup must not overwrite catalog recipes. Revised private instructions need explicit import.

## Tester feedback still open — not passing tests

- Add/remove confirmation should appear near the tapped control, especially the top toolbar.
- Taste Lab reportedly exits after one cycle: verify the three-plan flow. Align its design with suggestion review and consider **Save as draft** there.
- Allow password changes with the current password; email reset when it is forgotten. Confirm new-password matching and simplify the form.
- Show outstanding household invitations and allow cancellation.
- Clarify how family portions affect recipe servings; consider removing aisle reordering if it simplifies the app.
- Recovery after exhausting Taste Lab results needs to be noticeable.
- Far-future search ideas: themes such as chicken/rice, curry, beginner-friendly, date night, or unusual meals.

**Pending:** original #2 HTTP 405 trigger; smaller-phone visual verification. #24, #38, and #40 are proposals. Inline timers are deferred to the far future. Unbuilt features are tracked in [TODO](TODO.md), not daily tests.

## Report a problem

Give **screen + action + expected/actual result**, platform/build, text size, and a screenshot if useful. Confusing wording or awkward layout counts as a problem.

[Archived detailed checklist and original tester notes](archive/TESTER_CHECKLIST_2026-10-09.md) — reference only, not a daily assignment.

- [ ] **Taste Lab swipe history:** open beside Edit filters, change Like ↔ Pass, reopen/reload and confirm it saved. Back returns to the previous screen; failed saves show an error and keep the original vote.

- [ ] **Guest access:** use Plan, Recipes, Grocery, Prep, Filters, and Taste Lab signed out. Reopen and confirm data remains; a second browser must have a separate kitchen. Expired login must allow guest use. Create an account and confirm guest data carries over. Sign-in warnings must be dismissible and must not block features.

## TestFlight feedback: October 10, 2026

All twelve supplied reports were submitted from version **1.0.3 (2)**. They describe that installed build, not necessarily current main. No report is discarded merely because it is old. Branch `fix/testflight-feedback-oct10` starts from main `f97b6ae`.

| Folder suffix | Report | Disposition | Issues | Branches |
|---|---|---|---|---|
| base | Other-food search closes after one choice | Fixed in this branch: retain query and results, serialize saves | #85; #110 | issue-85-custom-food-search; fix/testflight-feedback-oct10 |
| 2 | Singular/plural duplicate food results | Already addressed by merged PR #98; retest against updated server | #85 | issue-85-custom-food-search |
| 3 | Prep feedback is too large and persistent | Fixed in this branch: compact Undo bar, four-second expiry, ratings in expanded rows | #78; #104; #110 | issue-78-prep-layout; fix/testflight-feedback-oct10 |
| 4 | Purple-star tips should remain hidden | Fixed in this branch for iOS and web; source inventory retained | #103 | fix/testflight-feedback-oct10 |
| 5 | Suggestions appear unexpectedly | Fixed delayed-completion reopening; saved suggestions no longer control presentation | #109; #26 | fix/testflight-feedback-oct10 |
| 6 | Closed suggestions will not reopen | Fixed: resume pending or in-flight proposal without another request | #109 | fix/testflight-feedback-oct10 |
| 7 | Four-meal plan does not fit iPhone 16 | Improved fixed layout after PR #80: 132-point photos at standard type, servings beside Schedule; device visual retest pending | #30; #35; #110 | codex/issue-30-four-meal-plan-fit; fix/testflight-feedback-oct10 |
| 8 | Plan menu New meal plan does nothing | Presentation moved to stable app root; menu action resumes/creates review | #109; #26 | fix/testflight-feedback-oct10 |
| 9 | Ingredient photos missing | Still a production configuration issue: garlic HTTP 404, GROCERY_PHOTO_DIR unset. Sixteen mapped photos prepared with checksums on existing volume path; production approval pending | #82; #18 | fix/testflight-feedback-oct10 (audit); Railway configuration |
| 10 | Complete all / Uncheck all should be one button | Fixed in iOS and web: one action based on completion state | #110 | fix/testflight-feedback-oct10 |
| 11 | Fill remaining plan using chosen meals | Added Fill in this plan. Keep selections; rank additions using ingredient reuse; active plan unchanged until approval | #88; #109 | fix/testflight-feedback-oct10 |
| 12 | Empty Grocery/Prep should offer Create meal plan | Fixed native actions: start suggestions directly when current plan is empty; Prep keeps Back to plan for a nonempty plan | #86; #109 | fix/testflight-feedback-oct10 |

Validation: affected API and recommendation suites; iOS simulator build; web production build. The Store suggestion methods are exercised with a delayed mock API for close-before-completion, reopening, duplicate taps, and error handling. Simulator installation stalled, so four-meal fit and native interaction still need a real-device or functioning simulator retest. These source fixes are not a new TestFlight release.

Ingredient gallery preparation: 16 currently mapped files, 26,393,274 bytes, SHA-256 manifest. Planned directory `/web/public/food/ingredient-photos-2026-10-10` on existing `weekplate-volume`; existing catalog and PostgreSQL storage are untouched. Enable via `GROCERY_PHOTO_DIR` only after production approval, then verify live mapped photo URLs.
