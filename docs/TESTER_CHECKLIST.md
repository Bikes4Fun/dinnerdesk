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
| **Weekend prep** | Items sit in food sections (Vegetables, Aromatics…, Protein, Sauces), one row per item even when several meals share it. Collapse and reopen a section with its arrow. Check an item: it leaves the list, the ring and its section bar move, and a bar offers Undo and 👍/👎 (👎 shows reasons). **Show completed** brings done items back faded. 👍/👎 on an unchecked item; 👎 asks why. Tap an item's name for each meal's step. Refresh: check-offs and votes stay. |
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
