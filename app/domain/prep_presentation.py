"""One prep instruction presentation contract for web, iOS and Android."""
from dataclasses import asdict, dataclass, field


@dataclass
class PrepInstructionGroup:
    text: str
    quantities: list[str]
    added: bool
    meals: list[dict] = field(default_factory=list)


class PrepTaskPresentation:
    """Group display instructions without losing quantities or source identities.

    Equal wording only shares a row when its amounts and household-added status
    also agree. Original steps remain unchanged for completion and feedback.
    """

    def __init__(self, task: dict):
        self.task = task

    def instruction_groups(self) -> list[dict]:
        groups: dict[tuple, PrepInstructionGroup] = {}
        for meal in self.task.get('meals') or []:
            steps = meal.get('steps') or [{'text': text} for text in meal.get('instructions') or []]
            for step in steps:
                text = (step.get('display_text') or step.get('text') or '').strip()
                if not text:
                    continue
                amounts = [q for q in step.get('quantities') or [] if q]
                added = bool(step.get('added'))
                key = (text.casefold(), tuple(amounts), added)
                group = groups.setdefault(key, PrepInstructionGroup(text, amounts, added))
                if not any(m['id'] == meal['id'] for m in group.meals):
                    group.meals.append({k: meal.get(k) for k in ('id', 'name', 'day')})
        return [asdict(group) for group in groups.values()]
