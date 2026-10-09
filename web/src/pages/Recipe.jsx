import { scaleAmount } from "../quantity.js";
import { useEffect, useRef, useState } from "react";
import { api, photoSrc } from "../api.js";
import { go } from "../nav.js";
import { parseIngLine } from "../parseIngredient.js";
import { asSlotIn, useWeek } from "../week.jsx";
import { RecipeEditorFields, serializeSteps, stepsFromRecipe } from "../RecipeEditor.jsx";
import { StepText, amountLines } from "../stepText.jsx";
import { StepTimers } from "../StepTimers.jsx";
import { Tip } from "../Tip.jsx";

function ingLines(recipe) {
  return (recipe.ingredients || [])
    .map((ing) => `${ing.quantity ? `${ing.quantity} ` : ""}${ing.name}`)
    .join("\n");
}

export function Recipe({ id }) {
  const week = useWeek();
  const [recipe, setRecipe] = useState(null);
  const [tab, setTab] = useState("overview");
  const [editing, setEditing] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState(false);
  const [name, setName] = useState("");
  const [servings, setServings] = useState(4);
  const [minutes, setMinutes] = useState("");
  const [ings, setIngs] = useState("");
  const [steps, setSteps] = useState([]);
  const [draftServings, setDraftServings] = useState(null);
  const [showMore, setShowMore] = useState(false);
  const moreRef = useRef(null);

  useEffect(() => {
    setAdded(false);
    setEditing(false);
    setDraftServings(null);
    setShowMore(false);
    api.recipe(id).then(setRecipe).catch((e) => setErr(e.message));
    week?.load?.().catch((e) => setErr(e.message));
  }, [id]);

  useEffect(() => {
    if (!showMore) return undefined;
    function onDoc(e) {
      if (!moreRef.current?.contains(e.target)) setShowMore(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [showMore]);

  function startEdit() {
    setName(recipe.name);
    setServings(recipe.servings);
    setMinutes(recipe.cooking_minutes == null ? "" : String(recipe.cooking_minutes));
    setIngs(ingLines(recipe));
    setSteps(stepsFromRecipe(recipe.instructions));
    setEditing(true);
    setShowMore(false);
    setErr("");
  }

  function editPayload() {
    return {
      name: name.trim(),
      servings: Number(servings) || 4,
      cooking_minutes: minutes === "" ? null : Number(minutes),
      ingredients: ings.split("\n").map(parseIngLine).filter(Boolean),
      instructions: serializeSteps(steps),
    };
  }

  async function saveEdit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const next = await api.patchRecipe(recipe.id, { in_place: true, ...editPayload() });
      setRecipe(next);
      setEditing(false);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveCopy() {
    setBusy(true);
    try {
      const next = await api.patchRecipe(recipe.id, { as_copy: true, ...editPayload() });
      setEditing(false);
      go(`/recipes/${next.id}`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function restoreOriginal() {
    setBusy(true);
    setShowMore(false);
    try {
      const next = await api.restoreRecipe(recipe.id);
      setRecipe(next);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleCookPrep(i) {
    const instructions = (recipe.instructions || []).map((s, j) => ({
      text: s.text || s.step || "",
      prep: j === i ? !s.prep : !!s.prep,
      ings: s.ings || "",
    }));
    try {
      const next = await api.patchRecipe(recipe.id, { in_place: true, instructions });
      setRecipe(next);
    } catch (e) {
      setErr(e.message);
    }
  }

  async function addToWeek() {
    setBusy(true);
    try {
      const plan = await api.plan();
      const slots = [
        ...plan.slots.map(asSlotIn),
        { recipe_id: recipe.id, day_index: null, meal_type: "dinner", servings: draftServings ?? recipe.servings },
      ];
      await api.putSlots(plan.id, slots);
      await week?.load?.();
      setAdded(true);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!recipe) return <div className="screen pad">{err || "Loading…"}</div>;

  const cookSteps = recipe.instructions || [];
  const planSlots = (week?.plan?.slots || []).filter((s) => s.recipe_id === recipe.id);
  const mealServings = planSlots.length
    ? planSlots[0].servings
    : (draftServings ?? recipe.servings ?? 4);

  async function bumpServings(delta) {
    const servings = Math.min(50, Math.max(1, (mealServings || 1) + delta));
    if (servings === mealServings) return;
    if (planSlots.length) {
      try {
        await Promise.all(planSlots.map((s) => api.patchSlot(s.id, { servings })));
        await week?.load?.();
      } catch (e) {
        setErr(e.message);
      }
      return;
    }
    setDraftServings(servings);
  }

  function ServingsMeta() {
    return (
      <p className="recipe-meta">
        <span className="meal-servings">
          <button
            type="button"
            className="meal-servings-btn"
            disabled={mealServings <= 1}
            aria-label="Fewer servings"
            onClick={() => bumpServings(-1)}
          >
            −
          </button>
          <span>{mealServings} servings</span>
          <button
            type="button"
            className="meal-servings-btn"
            disabled={mealServings >= 50}
            aria-label="More servings"
            onClick={() => bumpServings(1)}
          >
            +
          </button>
        </span>
        {recipe.cooking_minutes ? (
          <span className="recipe-cook-time">{recipe.cooking_minutes} min</span>
        ) : null}
      </p>
    );
  }

  return (
    <section className="screen">
      <header className="top sub">
        <button
          type="button"
          className="icon-btn"
          onClick={() => (editing ? setEditing(false) : go("/recipes"))}
          aria-label="Back"
        >
          ←
        </button>
        <h1>{editing ? "Edit recipe" : recipe.name}</h1>
        {!editing && (
          <div className="recipe-head-actions">
            <button
              type="button"
              className={`heart-btn${recipe.favorited ? " is-on" : ""}`}
              aria-label={recipe.favorited ? "Remove from your favorites" : "Save to your favorites"}
              onClick={() => {
                api.favorite(recipe.id, !recipe.favorited).then(setRecipe).catch((e) => setErr(e.message));
              }}
            >
              {recipe.favorited ? "♥" : "♡"}
            </button>
            <div className="add-menu-wrap" ref={moreRef}>
              <button
                type="button"
                className="heart-btn more-btn"
                aria-label="More"
                aria-expanded={showMore}
                aria-haspopup="menu"
                onClick={() => setShowMore((v) => !v)}
              >
                ⋯
              </button>
              {showMore && (
                <div className="add-menu" role="menu">
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setShowMore(false);
                      api
                        .tryLater(recipe.id, !recipe.to_try)
                        .then(setRecipe)
                        .catch((e) => setErr(e.message));
                    }}
                  >
                    {recipe.to_try ? "Remove from To try" : "To try"}
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setShowMore(false);
                      api
                        .hideRecipe(recipe.id, !recipe.hidden)
                        .then(setRecipe)
                        .catch((e) => setErr(e.message));
                    }}
                  >
                    {recipe.hidden ? "Unhide recipe" : "Hide Recipe"}
                  </button>
                  {recipe.catalog && recipe.edited ? (
                    <button type="button" role="menuitem" onClick={restoreOriginal} disabled={busy}>
                      Restore original
                    </button>
                  ) : null}
                </div>
              )}
            </div>
          </div>
        )}
      </header>
      {!editing && (
        <div className="tabs">
          {["overview", "cook"].map((t) => (
            <button key={t} type="button" className={`tab-btn${tab === t ? " is-on" : ""}`} onClick={() => setTab(t)}>
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
          <button type="button" className="tab-btn" onClick={startEdit}>
            Edit
          </button>
        </div>
      )}
      <div className="recipe-layout">
        {!editing && (
          <aside className="recipe-side">
            <ServingsMeta />
            <h3>Ingredients</h3>
            <ul className="plain">
              {recipe.ingredients.map((ing) => (
                <li key={`${ing.ingredient_id}-${ing.name}`}>
                  {ing.quantity ? `${scaleAmount(ing.quantity, recipe.servings, mealServings)} ` : ""}
                  {ing.name}
                </li>
              ))}
            </ul>
          </aside>
        )}
        <div className="scroll pad recipe-body">
          {err && <p className="banner err">{err}</p>}
          {editing ? (
            <form id="recipe-edit" onSubmit={saveEdit}>
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
                help={
                  recipe.catalog
                    ? "Save keeps this recipe id for this kitchen. Save as copy makes a new kitchen recipe and leaves the catalog dish alone."
                    : "Save updates this kitchen recipe."
                }
              />
            </form>
          ) : (
            <>
              {tab === "overview" && (
                <>
                  {recipe.photo_path && <img className="hero" src={photoSrc(recipe.photo_path)} alt="" />}
                  {recipe.photo_path && recipe.photo_ai && <Tip id="recipes.ai-photo" className="ai-photo-tip">This photo was made with AI. It shows the kind of dish, not this exact recipe.</Tip>}
                  <ServingsMeta />
                  {recipe.tags.length > 0 && (
                    <p className="muted">{recipe.tags.map((t) => t.replaceAll("_", " ")).join(" · ")}</p>
                  )}
                  <h3 className="ing-heading">Ingredients</h3>
                  <ul className="plain recipe-ings">
                    {recipe.ingredients.map((ing) => (
                      <li key={`ov-${ing.ingredient_id}-${ing.name}`}>
                        {ing.quantity ? `${scaleAmount(ing.quantity, recipe.servings, mealServings)} ` : ""}
                        {ing.name}
                      </li>
                    ))}
                  </ul>
                  <label className="block-label" htmlFor="dev-notes">
                    Dev notes
                  </label>
                  <textarea
                    id="dev-notes"
                    className="field dev-notes"
                    rows={4}
                    placeholder="Temporary scratch — sides to normalize, merge notes, etc."
                    defaultValue={recipe.dev_notes || ""}
                    key={recipe.id}
                    onBlur={(e) => {
                      const text = e.target.value;
                      if (text === (recipe.dev_notes || "")) return;
                      api.putDevNotes(recipe.id, text).then(setRecipe).catch((err) => setErr(err.message));
                    }}
                  />
                </>
              )}
              {tab === "cook" && (
                <ol className="steps">
                  {cookSteps.map((s, i) => (
                    <li key={i}>
                      <button
                        type="button"
                        className={`prep-tag${s.prep ? " is-on" : ""}`}
                        aria-pressed={!!s.prep}
                        onClick={() => toggleCookPrep(i)}
                      >
                        Prep
                      </button>
                      <StepText text={s.text || s.step || ""} />
                      <StepTimers text={s.text || s.step || ""} />
                      {s.ings ? (
                        <div className="step-ings">
                          <StepText text={amountLines(s.ings)} />
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ol>
              )}
            </>
          )}
        </div>
      </div>
      <footer className="dock">
        {editing ? (
          <>
            <button type="submit" form="recipe-edit" className="btn-primary block" disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </button>
            {recipe.catalog ? (
              <button type="button" className="btn-secondary block" disabled={busy} onClick={saveCopy}>
                Save as copy
              </button>
            ) : null}
          </>
        ) : (
          <button type="button" className="btn-primary block" disabled={busy || added} onClick={addToWeek}>
            {added ? "Added to this plan" : busy ? "Adding…" : "Add to this plan"}
          </button>
        )}
      </footer>
    </section>
  );
}
