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


class PrepMealPresentation:
    """The same prep tasks, grouped by the meal they're for (the Prep page's "By meal" view).

    Each meal lists its prep tasks in task order, each with only that meal's steps, so
    checking a task off for one meal never touches another meal. Meals are in cook-day
    order; unscheduled meals go last. Step keys and done state come straight from the
    task, so completion and feedback keep their original identities.
    """

    def __init__(self, tasks: list[dict]):
        self.tasks = tasks

    def meal_groups(self) -> list[dict]:
        groups: dict[int, dict] = {}
        for task in self.tasks:
            for meal in task.get('meals') or []:
                steps = []
                for step in meal.get('steps') or []:
                    text = (step.get('display_text') or step.get('text') or '').strip()
                    if text:
                        steps.append({'key': step.get('key'), 'text': text,
                                      'quantities': [q for q in step.get('quantities') or [] if q],
                                      'added': bool(step.get('added')), 'done': bool(step.get('done'))})
                if not steps:  # older cached tasks only carry plain instructions
                    steps = [{'key': None, 'text': text.strip(), 'quantities': [], 'added': False,
                              'done': bool(task.get('done'))}
                             for text in meal.get('instructions') or [] if text.strip()]
                if not steps:
                    continue
                group = groups.setdefault(meal['id'], {
                    'id': meal['id'], 'name': meal.get('name'), 'day': meal.get('day'),
                    'day_index': meal.get('day_index'), 'tasks': []})
                quantities = []
                for step in steps:
                    quantities += [q for q in step['quantities'] if q not in quantities]
                group['tasks'].append({
                    'task_id': task.get('id'), 'title': task.get('title'), 'quantities': quantities,
                    'storage': task.get('storage') or '', 'done': all(s['done'] for s in steps),
                    'steps': steps})
        ordered = sorted(groups.values(), key=lambda g: (g['day_index'] is None, g['day_index'] or 0))
        return ordered
