# Even issue pass — October 8, 2026

The branches are cumulative: each starts from the preceding issue branch. All are local.
`codex/even-issues-validation` includes every implementation, proposal, and final validation.
Implementation is complete for the fixes below; device/browser visual verification remains.
Issues have not been closed or deployed.

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
| #24 | `codex/issue-24-tour-order` | [Tour order proposal](proposals/issue-24-tour-order.md), pending choice |
| #26 | `codex/issue-26-plan-menu` | Remove unrequested chooser menu and unused chooser code |
| #28 | `codex/issue-28-prep-completion` | One PUT endpoint, one JSON store, legacy migration; updated API/app must ship together |
| #30 | `codex/issue-30-plan-list-layout` | Full names and Schedule without shrinking photos |
| #32 | `codex/issue-32-decline-in-place` | Retain review during replacement; failure supports retry |
| #34 | `codex/issue-34-grocery-heading` | Full-width secondary usage heading |
| #36 | `codex/issue-36-tab-reselection` | Same-tab selection returns to root |
| #38 | `codex/issue-38-category-preferences` | [Category proposal](proposals/issue-38-category-preferences.md), pending choice |
| #40 | `codex/issue-40-more-navigation` | [More grouping proposal](proposals/issue-40-more-navigation.md), pending choice |

Validation: 197 Python tests pass in a dedicated local test database; iPhone Debug simulator
build succeeds without signing; web production build and Taste Lab JavaScript syntax checks
pass. Test isolation now resets Taste Lab's cached initializer between fresh database schemas.

Use [the tester checklist](TESTER_CHECKLIST.md), particularly the Even issue verification
section, for large text, narrow screens, VoiceOver, error/retry states, and visual review.
Issue #2's underlying 405 trigger remains unresolved; request diagnostics are in place.
