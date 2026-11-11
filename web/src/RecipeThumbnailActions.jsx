import { useState } from "react";
import { api } from "./api.js";
import { useWeek } from "./week.jsx";

export function RecipeThumbnailActions({ recipe, onChange, inline = false }) {
  const [busy, setBusy] = useState(false);
  const { toast } = useWeek();
  async function toggle(e, field) {
    e.preventDefault(); e.stopPropagation(); setBusy(true);
    try {
      const on = !recipe[field];
      const next = field === "reviewed" ? await api.reviewRecipe(recipe.id, on)
        : await api.recipeWorkflow(recipe.id, { to_edit: on });
      onChange({ id: recipe.id, [field]: next[field] });
    } catch (e) { toast(e.message); }
    finally { setBusy(false); }
  }
  return (
    <div className={`card-admin-actions${inline ? " is-inline" : ""}`}>
    <button type="button" className="card-review" aria-pressed={Boolean(recipe.reviewed)} disabled={busy}
      aria-label={`${recipe.reviewed ? "Remove review from" : "Mark reviewed:"} ${recipe.name}`}
      onClick={(e) => toggle(e, "reviewed")}>{recipe.reviewed ? "✓ Reviewed" : "Review"}</button>
    <button type="button" className="card-review" aria-pressed={Boolean(recipe.to_edit)} disabled={busy}
      aria-label={`${recipe.to_edit ? "Remove from To edit:" : "Tag as To edit:"} ${recipe.name}`}
      onClick={(e) => toggle(e, "to_edit")}>{recipe.to_edit ? "✓ To edit" : "To edit"}</button>
    </div>
  );
}
