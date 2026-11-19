import { useEffect, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";

const QUEUES = [
  ["to_edit", "To edit", "Remove To edit tag"],
  ["hidden", "Hidden from everyone", "Show to everyone"],
  ["delete_requested", "Deletion review", "Keep recipe"],
];

export function RecipeFlags() {
  const [data, setData] = useState(null);
  const [queue, setQueue] = useState("to_edit");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.flaggedRecipes().then(setData).catch((e) => setErr(e.message)); }, []);

  async function resolve(recipe) {
    setBusy(true);
    setErr("");
    try {
      if (queue === "hidden") await api.retireRecipe(recipe.id, false);
      else await api.recipeWorkflow(recipe.id, { [queue]: false });
      setData(await api.flaggedRecipes());
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }

  const rows = data?.queues?.[queue] || [];
  return (
    <section className="screen">
      <header className="top sub">
        <button type="button" className="icon-btn" onClick={() => go("/settings")} aria-label="Back">←</button>
        <h1>Recipes to edit</h1><span />
      </header>
      <div className="scroll pad ingredient-review">
        <p>Manage recipes tagged for editing, hidden from everyone, or awaiting deletion review. Nothing here deletes a recipe.</p>
        {err && <p className="banner err" role="alert">{err}</p>}
        {!data ? <p>Loading recipes…</p> : <>
          <div className="tabs" role="group" aria-label="Recipe review lists">
            {QUEUES.map(([id, title]) => (
              <button key={id} type="button" className={`tab-btn${queue === id ? " is-on" : ""}`}
                aria-pressed={queue === id} disabled={busy} onClick={() => setQueue(id)}>
                {title} ({data.queues?.[id]?.length || 0})
              </button>
            ))}
            <button type="button" className={`tab-btn${queue === "ingredients" ? " is-on" : ""}`}
              aria-pressed={queue === "ingredients"} disabled={busy} onClick={() => setQueue("ingredients")}>
              Ingredient fixes ({data.count})
            </button>
          </div>
          {queue === "ingredients" ? <>
            <p className="banner review-only">Ingredient text flagged for a hand edit. Open the recipe to fix it.</p>
            {data.reasons.map((bucket) => (
              <article className="review-card" key={bucket.reason}>
                <div className="review-progress"><span>{bucket.reason}</span><span>{bucket.count}</span></div>
                <div className="review-recipes">
                  {bucket.recipes.map((recipe, index) => (
                    <div className="review-recipe" key={`${recipe.source}-${recipe.name}-${recipe.raw}-${index}`}>
                      {recipe.recipe_id
                        ? <button type="button" className="text-link" onClick={() => go(`/recipes/${recipe.recipe_id}`)}>{recipe.name}</button>
                        : <strong>{recipe.name}</strong>}
                      <small>{recipe.source} · {recipe.ingredient_name} · “{recipe.raw}”</small>
                      {recipe.source_url && <a href={recipe.source_url} target="_blank" rel="noreferrer">View source</a>}
                    </div>
                  ))}
                </div>
              </article>
            ))}
            {data.reasons.length === 0 && <p>No ingredient fixes queued.</p>}
          </> : <>
            {rows.length === 0 && <p>No recipes in this list.</p>}
            {rows.map((recipe) => (
              <article className="review-card" key={recipe.id}>
                <h2><a href={`/recipes/${recipe.id}`} onClick={(e) => { e.preventDefault(); go(`/recipes/${recipe.id}`); }}>{recipe.name}</a></h2>
                <button type="button" className="btn-secondary" disabled={busy} onClick={() => resolve(recipe)}>
                  {QUEUES.find(([id]) => id === queue)?.[2]}
                </button>
              </article>
            ))}
          </>}
        </>}
      </div>
    </section>
  );
}
