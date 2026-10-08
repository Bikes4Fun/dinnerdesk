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
  const [toast, setToastMsg] = useState("");
  const weekIds = useMemo(() => new Set((plan?.slots || []).map((s) => s.recipe_id)), [plan]);

  async function load() {
    setPlan(await api.plan());
  }

  useEffect(() => {
    load().catch((e) => toastMsg(e.message));
  }, []);

  function toastMsg(text) {
    setToastMsg(text);
    window.clearTimeout(toastMsg._t);
    toastMsg._t = window.setTimeout(() => setToastMsg(""), 2200);
  }

  async function toggleRecipe(recipe) {
    if (!plan) await load();
    const current = plan || (await api.plan());
    const on = current.slots.some((s) => s.recipe_id === recipe.id);
    const slots = on
      ? current.slots.filter((s) => s.recipe_id !== recipe.id).map(asSlotIn)
      : [
          ...current.slots.map(asSlotIn),
          { recipe_id: recipe.id, day_index: null, meal_type: "dinner", servings: recipe.servings },
        ];
    const next = await api.putSlots(current.id, slots);
    setPlan(next);
    toastMsg(on ? "Removed" : "Added to plan");
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
      {toast ? <div className="toast">{toast}</div> : null}
    </Week.Provider>
  );
}
