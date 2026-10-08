import { useEffect, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";

export function RecipeFlags() {
  const [data, setData] = useState({ count: 0, reasons: [] });
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .flaggedRecipes()
      .then(setData)
      .catch((error) => setErr(error.message));
  }, []);

  return (
    <section className="screen">
      <header className="top sub">
        <button type="button" className="icon-btn" onClick={() => go("/settings")} aria-label="Back">
          ←
        </button>
        <h1>Recipes to edit</h1>
        <span />
      </header>
      <div className="scroll pad ingredient-review">
        <p className="banner review-only">
          {data.count} recipes whose ingredient text needs a hand edit. Nothing is changed until you
          edit the recipe.
        </p>
        {err ? <p className="banner err">{err}</p> : null}
        {data.reasons.map((bucket) => (
          <article className="review-card" key={bucket.reason}>
            <div className="review-progress">
              <span>{bucket.reason}</span>
              <span>{bucket.count}</span>
            </div>
            <div className="review-recipes">
              {bucket.recipes.map((recipe, index) =>
                recipe.source_url ? (
                  <a
                    className="review-recipe"
                    href={recipe.source_url}
                    target="_blank"
                    rel="noreferrer"
                    key={`${recipe.source}-${recipe.name}-${recipe.raw}-${index}`}
                  >
                    <strong>{recipe.name}</strong>
                    <small>
                      {recipe.source} · {recipe.ingredient_name} · “{recipe.raw}”
                    </small>
                  </a>
                ) : (
                  <div
                    className="review-recipe"
                    key={`${recipe.source}-${recipe.name}-${recipe.raw}-${index}`}
                  >
                    <strong>{recipe.name}</strong>
                    <small>
                      {recipe.source} · {recipe.ingredient_name} · “{recipe.raw}”
                    </small>
                  </div>
                ),
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
