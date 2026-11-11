import FoodPhoto from "./FoodPhoto.jsx";
import { ReviewedBadge } from "./ReviewedBadge.jsx";
import { RecipeReviewButton } from "./RecipeReviewButton.jsx";
import { api } from "./api.js";
import { go } from "./nav.js";
import { useWeek } from "./week.jsx";

export function hasTag(r, tag) {
  return (r.tags || []).includes(tag);
}

// A catalog recipe with our photo whose steps aren't written yet: shown dimmed, can't be opened.
function ComingSoonPhoto({ path, className }) {
  return (
    <div className="coming-soon" aria-label="Coming soon">
      <FoodPhoto className={className} path={path} />
      <span className="coming-soon-tag">Coming soon</span>
    </div>
  );
}

export function RecipeCard({ recipe, onChange, admin = false }) {
  if (recipe.coming_soon) {
    return (
      <div className="card is-coming-soon" aria-disabled={admin ? undefined : true}>
        <div className="card-img"><ComingSoonPhoto path={recipe.photo_path} />
          {admin && <RecipeReviewButton recipe={recipe} onChange={onChange} />}
        </div>
        <p className="card-name">{recipe.name}</p>
        <ReviewedBadge reviewed={recipe.reviewed} />
      </div>
    );
  }
  return <ReadyRecipeCard recipe={recipe} onChange={onChange} admin={admin} />;
}

function ReadyRecipeCard({ recipe, onChange, admin }) {
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
        {admin && <RecipeReviewButton recipe={recipe} onChange={onChange} />}
      </div>
      <button type="button" className="card-open" onClick={() => go(`/recipes/${recipe.id}`)}>
        <p className="card-name">{recipe.name}</p>
        <ReviewedBadge reviewed={recipe.reviewed} />
      </button>
    </div>
  );
}

export function RecipeRow({ recipe, onChange, admin = false }) {
  if (recipe.coming_soon) {
    return (
      <div className="recipe-row is-coming-soon" aria-disabled={admin ? undefined : true}>
        <div className="thumb-wrap"><ComingSoonPhoto className="thumb-sq" path={recipe.photo_path} />
          {admin && <RecipeReviewButton recipe={recipe} onChange={onChange} />}
        </div>
        <div className="recipe-copy"><strong>{recipe.name}</strong><ReviewedBadge reviewed={recipe.reviewed} /></div>
      </div>
    );
  }
  return <ReadyRecipeRow recipe={recipe} onChange={onChange} admin={admin} />;
}

function ReadyRecipeRow({ recipe, onChange, admin }) {
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
        {admin && <RecipeReviewButton recipe={recipe} onChange={onChange} />}
      </div>
      <button type="button" className="recipe-copy" onClick={() => go(`/recipes/${recipe.id}`)}>
        <strong>{recipe.name}</strong>
        <ReviewedBadge reviewed={recipe.reviewed} />
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
