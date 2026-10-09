# Dinnerdesk tester checklist

*Updated Oct 9, 2026 · Branch: `merge_all_issues` · Record the app/server version you actually test.*

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
| **Suggestion layout** | Four meals fit on most phones at normal text size. Full names, circular swap icons, and adjacent decisions remain readable. At large text, scroll to every action. |
| **Decline / retry** | Decline replaces only the proposal. A failed replacement offers **Try another suggestion**; a declined plan cannot be approved or edited. |
| **Recipe detail** | ⋯ stays open and all options are reachable. Favorite, To try, Hide/Unhide, servings, Edit/Restore, and instruction attribution work. Search uses the cream palette. |
| **Taste Lab** | Like/pass, swap/More options, and reject work. Verify three approvals before “You’re set”; **Done for now** ends early. Empty results offer noticeable recovery. |
| **Plan / drafts** | Full names, Schedule, Edit → Done, servings, cooked/undo, and removal confirmation work. Save/load a draft; history has readable details and delete buttons. Active plan is protected. |
| **Filters** | Search “bell peppers” or “ground”; explicitly select a food, reopen, then remove it. Unknown searches show no unrelated results. **None** clears selections. |
| **Grocery / kitchen** | Missing photos leave no empty box. Substitute an item without leaving its detail. Long names wrap; pantry, portions, stores/aisles, and completed-item controls persist. |
| **Weekend prep** | Shared prep combines correctly. Expand/collapse; check a step and a whole task; refresh. Completion survives unchanged-step regrouping. |
| **Navigation / account** | Selected tab is obvious without color; tapping it returns to its root. Email appears once, household name saves, and reset email sends only when tapped. |

## Before a release — not daily

- [ ] **Accessibility:** smaller phone, largest text, narrow web window, and VoiceOver. Check recipe, suggestion, Grocery, and Prep screens; no clipped names, overlap, or unreachable decisions.
- [ ] **Account access:** sign-up/sign-in/out, password reset, invite/join/remove a household member. Removed members lose access; shared data matches across app and web.
- [ ] **Recovery and persistence:** failed requests show readable retry guidance; pending proposals and saved edits survive restart. Verify search, share/print, and tour skip/replay.
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
