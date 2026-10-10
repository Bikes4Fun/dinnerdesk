import FoodPhoto from "./FoodPhoto.jsx";
import { api } from "./api.js";
import { go } from "./nav.js";
import { useWeek } from "./week.jsx";

export function hasTag(r, tag) {
  return (r.tags || []).includes(tag);
}

export function RecipeCard({ recipe, onChange }) {
  const { weekIds, toggleRecipe } = useWeek();
  const on = weekIds.has(recipe.id);

  async function heart(e) {
    e.stopPropagation();
    try {
      const next = await api.favorite(recipe.id, !recipe.favorited);
      onChange?.({ ...recipe, favorited: next.favorited });
    } catch (error) { throw error; }
  }

  return (
    <div className="card">
      <div className="card-img">
        <button type="button" className="card-open" onClick={() => go(`/recipes/${recipe.id}`)}>
          <FoodPhoto path={recipe.photo_path} />
        </button>
        <button
          type="button"
          className={`card-heart${recipe.favorited ? " is-on" : ""}`}
          aria-label={recipe.favorited ? "Remove from your favorites" : "Save to your favorites"}
          onClick={heart}
        >
          {recipe.favorited ? "♥" : "♡"}
        </button>
        <button
          type="button"
          className={`card-add${on ? " is-on" : ""}`}
          aria-label={on ? "Already on plan" : "Add to plan"}
          onClick={() => { if (!on) toggleRecipe(recipe); }}
        >
          {on ? "✓" : "+"}
        </button>
      </div>
      <button type="button" className="card-open" onClick={() => go(`/recipes/${recipe.id}`)}>
        <p className="card-name">{recipe.name}</p>
      </button>
    </div>
  );
}

export function RecipeRow({ recipe, onChange }) {
  const { weekIds, toggleRecipe } = useWeek();
  const on = weekIds.has(recipe.id);

  async function heart(e) {
    e.stopPropagation();
    try {
      const next = await api.favorite(recipe.id, !recipe.favorited);
      onChange?.({ ...recipe, favorited: next.favorited });
    } catch (error) { throw error; }
  }

  return (
    <div className="recipe-row">
      <div className="thumb-wrap">
        <button type="button" className="recipe-open-photo" onClick={() => go(`/recipes/${recipe.id}`)}>
          <FoodPhoto className="thumb-sq" path={recipe.photo_path} />
        </button>
        <button
          type="button"
          className={on ? "check-circle" : "add-circle"}
          aria-label={on ? "Already on plan" : "Add to plan"}
          onClick={() => { if (!on) toggleRecipe(recipe); }}
        >
          {on ? "✓" : "+"}
        </button>
      </div>
      <button type="button" className="recipe-copy" onClick={() => go(`/recipes/${recipe.id}`)}>
        <strong>{recipe.name}</strong>
      </button>
      <button
        type="button"
        className={`row-heart${recipe.favorited ? " is-on" : ""}`}
        aria-label={recipe.favorited ? "Remove from your favorites" : "Save to your favorites"}
        onClick={heart}
      >
        {recipe.favorited ? "♥" : "♡"}
      </button>
    </div>
  );
}
