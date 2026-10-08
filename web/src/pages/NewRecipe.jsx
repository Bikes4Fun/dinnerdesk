import { useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";
import { parseIngLine } from "../parseIngredient.js";
import { RecipeEditorFields, emptyStep, serializeSteps } from "../RecipeEditor.jsx";

function fromUrlMode() {
  return new URLSearchParams(window.location.search).get("from") === "url";
}

export function NewRecipe() {
  const byUrl = fromUrlMode();
  const [name, setName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [servings, setServings] = useState(4);
  const [minutes, setMinutes] = useState("");
  const [ings, setIngs] = useState("1 onion\n2 cloves garlic");
  const [steps, setSteps] = useState([emptyStep()]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const ingredients = ings.split("\n").map(parseIngLine).filter(Boolean);
      const recipe = await api.createRecipe({
        name,
        servings: Number(servings) || 4,
        cooking_minutes: minutes === "" ? null : Number(minutes),
        source_url: sourceUrl.trim(),
        ingredients,
        instructions: serializeSteps(steps),
        cookware: [],
        tags: ["custom"],
      });
      go(`/recipes/${recipe.id}`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="screen">
      <header className="top sub">
        <button type="button" className="icon-btn" onClick={() => go("/recipes")} aria-label="Back">
          ←
        </button>
        <h1>{byUrl ? "Add by URL" : "New recipe"}</h1>
      </header>
      <form className="scroll pad" onSubmit={onSubmit}>
        {err && <p className="banner err">{err}</p>}
        {byUrl && (
          <>
            <label className="block-label">Recipe URL</label>
            <input
              className="field"
              type="url"
              required
              placeholder="https://"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
            />
          </>
        )}
        <RecipeEditorFields
          name={name}
          setName={setName}
          servings={servings}
          setServings={setServings}
          minutes={minutes}
          setMinutes={setMinutes}
          ings={ings}
          setIngs={setIngs}
          steps={steps}
          setSteps={setSteps}
          help="Save creates a kitchen recipe. It does not write catalog."
        />
        <button type="submit" className="btn-primary block" disabled={busy}>
          {busy ? "Saving…" : "Save recipe"}
        </button>
      </form>
    </section>
  );
}
