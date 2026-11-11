# User-visible changes — November 11

Scope: today's recipe/prep changes for ordinary users. Recipe approval, edit/hide/delete
queues, thumbnail action buttons and inline catalog editing are web administration tools.

| User-visible behavior | Web | iOS | Android |
| --- | --- | --- | --- |
| Reviewed recipe badge and filter | Present | Present | Present |
| Reviewed overlay on main photo and recipe thumbnails | Present | Added native overlays | Added native overlays |
| Tested-photo badge, recorded credit and source link | Present | Present | Added gallery metadata and display |
| Multiple distinct photos, per-photo AI/shared/tested notes | Present | Present | Added read-only gallery paging |
| Exact duplicate images appear once, preserving status flags | Shared API | Shared API | Shared API |
| Prep instructions, amounts, storage and grouped wording | Shared API/presentation | Shared API/presentation | Shared API/presentation |
| Prep votes with optional reasons/notes, missing-step additions | Present | Present | Present |
| Remove steps when editing a household recipe | Remove button | Swipe to delete | Delete button |
| Unfinished template creation | Disabled Coming soon preview (#320) | Inactive Coming soon section | Inactive Coming soon section |

Reviewed is content approval; the tested-photo mark records a photo of the recipe as cooked.
The names and accessible explanations now share `ios/dinnerdesk/copy.json` across clients.
The tested label remains Developer tested pending the user's wording choice.

Validation uses `tests/fixtures/recipe_photo_status.json` in web rendering, Android model
tests and the standalone iOS model check. Mac CI runs the Swift check and app build.
Device checks remain: compare the same recipe's badges, credit/source and photo paging;
try the Reviewed filter; compare prep wording/feedback; check that native screens have no
recipe-approval checkbox. This is not a completion claim for the wider issue #288 audit.
