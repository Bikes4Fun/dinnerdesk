/** Shared prep presentation adapter; the server owns grouping for all clients. */
export class PrepTaskPresentation {
  constructor(task) {
    this.task = task;
  }

  get instructionGroups() {
    if (Array.isArray(this.task.instruction_groups)) return this.task.instruction_groups;
    // Older cached responses remain readable during server/app rollout.
    const groups = [];
    for (const meal of this.task.meals || []) {
      const steps = meal.steps?.length ? meal.steps : (meal.instructions || []).map((text) => ({ text }));
      for (const step of steps) {
        const text = (step.display_text || step.text || "").trim();
        if (!text) continue;
        const quantities = (step.quantities || []).filter(Boolean);
        const added = Boolean(step.added);
        const link = { id: meal.id, name: meal.name, day: meal.day ?? null };
        const shared = groups.find((g) => g.text.toLowerCase() === text.toLowerCase()
          && JSON.stringify(g.quantities) === JSON.stringify(quantities) && g.added === added);
        if (shared) {
          if (!shared.meals.some((m) => m.id === meal.id)) shared.meals.push(link);
        } else {
          groups.push({ text, quantities, added, meals: [link] });
        }
      }
    }
    return groups;
  }
}

/** The same tasks grouped by meal ("By meal" view). The server sends `meal_groups`; this
 *  fallback rebuilds them for older cached responses. An empty server list is authoritative. */
export function prepMealGroups(data) {
  if (Array.isArray(data?.meal_groups)) return data.meal_groups;
  const groups = new Map();
  for (const task of data?.tasks || []) {
    for (const meal of task.meals || []) {
      let steps = (meal.steps || []).map((step) => ({
        key: step.key ?? null,
        text: (step.display_text || step.text || "").trim(),
        quantities: (step.quantities || []).filter(Boolean),
        added: Boolean(step.added),
        done: Boolean(step.done),
      })).filter((step) => step.text);
      if (!steps.length) {
        steps = (meal.instructions || []).map((text) => text.trim()).filter(Boolean)
          .map((text) => ({ key: null, text, quantities: [], added: false, done: Boolean(task.done) }));
      }
      if (!steps.length) continue;
      if (!groups.has(meal.id)) {
        groups.set(meal.id, { id: meal.id, name: meal.name, day: meal.day ?? null, day_index: meal.day_index ?? null, tasks: [] });
      }
      const quantities = [];
      for (const step of steps) for (const q of step.quantities) if (!quantities.includes(q)) quantities.push(q);
      groups.get(meal.id).tasks.push({
        task_id: task.id, title: task.title, quantities, storage: task.storage || "",
        done: steps.every((step) => step.done), steps,
      });
    }
  }
  return [...groups.values()].sort((a, b) =>
    (a.day_index == null) - (b.day_index == null) || (a.day_index ?? 0) - (b.day_index ?? 0));
}
