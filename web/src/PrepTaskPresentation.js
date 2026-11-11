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
