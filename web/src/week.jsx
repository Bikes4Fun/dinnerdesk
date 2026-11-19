import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

export function asSlotIn(s) {
  return {
    id: s.id,
    recipe_id: s.recipe_id,
    day_index: s.day_index,
    meal_type: s.meal_type,
    servings: s.servings,
  };
}

const Week = createContext(null);

export function useWeek() {
  return useContext(Week);
}

export function WeekProvider({ children }) {
  const [plan, setPlan] = useState(null);
  // { text, undo? }: an error message, or what a card's + just did and how to take it back.
  const [toast, setToast] = useState(null);
  const weekIds = useMemo(() => new Set((plan?.slots || []).map((s) => s.recipe_id)), [plan]);

  async function load() {
    setPlan(await api.plan());
  }

  useEffect(() => {
    load().catch((e) => toastMsg(e.message));
  }, []);

  function toastMsg(text, undo) {
    setToast(text ? { text, undo } : null);
    window.clearTimeout(toastMsg._t);
    // An undo needs time to be read and tapped; a plain message doesn't.
    toastMsg._t = window.setTimeout(() => setToast(null), undo ? 6000 : 2200);
  }

  /// Puts a recipe on this week's plan or takes it off. `from` is the plan to change, for an
  /// undo that must work from the plan the change produced rather than this render's copy.
  async function setOnPlan(recipe, on, from) {
    const current = from || plan || (await api.plan());
    const slots = on
      ? [
          ...current.slots.map(asSlotIn),
          { recipe_id: recipe.id, day_index: null, meal_type: "dinner" },
        ]
      : current.slots.filter((s) => s.recipe_id !== recipe.id).map(asSlotIn);
    const next = await api.putSlots(current.id, slots);
    setPlan(next);
    return next;
  }

  async function toggleRecipe(recipe) {
    const current = plan || (await api.plan());
    const on = current.slots.some((s) => s.recipe_id === recipe.id);
    const next = await setOnPlan(recipe, !on, current);
    // The card's + and check carry no label (#35), so say what happened and offer one undo.
    toastMsg(on ? "Removed from this week" : "Added to this week", () => setOnPlan(recipe, on, next));
    return next;
  }

  async function putSlots(slots) {
    const next = await api.putSlots(plan.id, slots);
    setPlan(next);
    return next;
  }

  return (
    <Week.Provider value={{ plan, weekIds, load, toggleRecipe, putSlots, toast: toastMsg }}>
      {children}
      {toast ? (
        <div className="toast" role="status" aria-live="polite">
          <span className="toast-text">{toast.text}</span>
          {toast.undo && (
            <button type="button" className="toast-undo" onClick={() => { setToast(null); toast.undo(); }}>Undo</button>
          )}
          <button type="button" className="toast-x" aria-label="Dismiss" onClick={() => setToast(null)}>×</button>
        </div>
      ) : null}
    </Week.Provider>
  );
}
