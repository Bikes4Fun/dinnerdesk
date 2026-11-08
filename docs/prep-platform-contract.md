# Shared prep system

Prep selection, ingredient matching, contextual wording, quantities, batching,
section assignment and storage guidance belong to `SemanticPrepEngine` on the
server. All clients use the same plan/prep API; none implement their own selection
rules. The existing function entry points remain compatibility adapters, including
ingredient vocabulary used by recipe normalization.

`PrepTaskPresentation` creates `instruction_groups` after cook dates are attached
to meals. Each group contains `text`, `quantities`, `added`, and meal links with
`id`, `name`, and `day`. Instructions only share a group when their wording,
amounts and household-added status agree. Original `meals[].steps[].text` and
`key` remain authoritative for feedback and completion.

The web adapter class and native presentation classes consume server groups.
They provide the same fallback for older cached responses during app/server
rollouts. iOS keeps SwiftUI views and decoded value models as structs; Android
keeps Compose functions and serializable data classes. Behavior belongs to the
engine and presentation classes, using each framework's intended view types.

| Prep capability | Web | iOS | Android | Owner |
| --- | --- | --- | --- | --- |
| Selection, batching, quantities and storage rules | API | API | API | SemanticPrepEngine |
| Clarified instructions and per-step amounts | Yes | Yes | Yes | Shared API contract |
| Distinct amounts / added status remain distinct | Yes | Yes | Yes | PrepTaskPresentation |
| Storage guidance | Yes | Yes | Yes | Shared API contract |
| Original feedback and completion identities | Yes | Yes | Yes | Shared API and stores |
| Meal links and cook dates | Yes | Yes | Yes | Shared API and platform navigation |
| Completion, undo, ratings, missing-step additions | Existing | Existing | Existing | Shared API and platform stores |
| Feedback inbox administration | Yes | Intentional exclusion | Intentional exclusion | Web administration |

The fixture `tests/fixtures/prep_presentation.json` is consumed by Python, Node,
Android JUnit and the standalone iOS model check. It covers matching wording with
different quantities, shared meal links, household-added status, legacy cached
instructions, and unchanged source identities. An empty server group list is
authoritative and must not trigger fallback.

Validation commands:

- Python: `pytest tests/test_prep.py tests/test_prep_presentation.py tests/test_api.py -k prep`
- Web: `node --test tests/prep-presentation.test.js` and `npm run build` in `web/`.
- Android: `gradlew testDebugUnitTest assembleDebug` in `android/` with JDK 17.
- iOS (Mac/Xcode): `python3 ios/tests/test_prep_presentation.py`, followed by an app build.

Manual checks on each platform: open the same plan containing recipes 57, 379,
14/138, 15/51 and 244; compare display wording, amounts, storage and meal links;
then verify completion/undo, ratings and missing-step addition/removal. Overall
application parity beyond this prep work is tracked separately in issue #288.
