# Kitchen-tested

One recipe status, edited only by DinnerDesk admins on web. The existing protected
`PUT /api/recipes/{id}/reviewed` endpoint and `reviewed` boolean remain the storage/API
contract for compatibility with shipped clients; existing admin marks are preserved.
New clients label that same boolean Kitchen-tested everywhere. No photo is created or
changed by marking a recipe. Legacy photo-level `tested` metadata remains attribution
data and no longer creates a separate visible status.

Feed cards/rows show cook time and the aubergine seal/check status below the title.
The recipe page shows a tappable tinted chip below the title, opening an explanation
sheet. Shared wording lives in `ios/dinnerdesk/copy.json`; the sheet does not claim
specific timing, temperature, quantity or serving checks that have not been confirmed.
Catalog administration is web-only; user recipe editing and household roles remain.

The gallery uses the shared server duplicate-photo matching from #323. Different
photos remain pageable and retain their recorded credits. A status never adds a slide.

Manual checks are in `docs/TESTER_CHECKLIST.md` under Kitchen-tested recipe status.
