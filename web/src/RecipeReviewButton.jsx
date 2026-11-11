import { useState } from "react";
import { api } from "./api.js";
import { useWeek } from "./week.jsx";

export function RecipeReviewButton({ recipe, onChange }) {
  const [busy, setBusy] = useState(false);
  const { toast } = useWeek();
  return (
    <button type="button" className="card-review" aria-pressed={Boolean(recipe.reviewed)} disabled={busy}
      aria-label={`${recipe.reviewed ? "Remove review from" : "Mark reviewed:"} ${recipe.name}`}
      onClick={async (e) => {
        e.preventDefault(); e.stopPropagation(); setBusy(true);
        try {
          const next = await api.reviewRecipe(recipe.id, !recipe.reviewed);
          onChange({ ...recipe, reviewed: next.reviewed });
        } catch (e) { toast(e.message); }
        finally { setBusy(false); }
      }}>{recipe.reviewed ? "✓ Reviewed" : "Review"}</button>
  );
}
