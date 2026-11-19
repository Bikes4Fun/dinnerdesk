import FoodPhoto from "../FoodPhoto.jsx";
import { RecipeGallery } from "../RecipeGallery.jsx";
import { ReviewedBadge } from "../ReviewedBadge.jsx";
import { scaleAmount } from "../quantity.js";
import { useEffect, useRef, useState } from "react";

const SIDE_MIN = 200;
const SIDE_BOTH = 480;
const PHOTO_MIN = 160;

function storedSide() {
  try {
    const n = Number(localStorage.getItem("recipeSide"));
    if (Number.isFinite(n)) return n;
  } catch {
    /* storage off */
  }
  return 260;
}
import { api } from "../api.js";
import { go } from "../nav.js";
import { parseIngLine } from "../parseIngredient.js";
import { asSlotIn, useWeek } from "../week.jsx";
import { RecipeEditorFields, serializeSteps, stepsFromRecipe } from "../RecipeEditor.jsx";
import { StepText, amountLines } from "../stepText.jsx";
// Far-future feature: inline recipe timers are disabled.
// import { StepTimers } from "../StepTimers.jsx";
import { Tip } from "../Tip.jsx";
import { REPORT_REASONS } from "../reportOptions.js";

function ingLines(recipe) {
  return (recipe.ingredients || [])
    .map((ing) => `${ing.quantity ? `${ing.quantity} ` : ""}${ing.name}`)
    .join("\n");
}

/** The site a kitchen recipe came from, for its credit link; only http(s) links count. */
function sourceHost(url) {
  try {
    const u = new URL(url || "");
    return u.protocol === "http:" || u.protocol === "https:" ? u.hostname.replace(/^www\./, "") : "";
  } catch {
    return "";
  }
}

export function Recipe({ id }) {
  const week = useWeek();
  const [recipe, setRecipe] = useState(null);
  const [tab, setTab] = useState("overview");
  const layoutRef = useRef(null);
  const [side, setSide] = useState(storedSide);
  const [desktop, setDesktop] = useState(() => window.matchMedia("(min-width: 880px)").matches);
  const both = desktop && side >= SIDE_BOTH;
  const [editing, setEditing] = useState(false);
  // A kitchen edits its own recipes; catalog edits are for Dinnerdesk admins only, and the
  // server refuses everyone else too.
  const [admin, setAdmin] = useState(false);
  const canEdit = admin || recipe?.catalog === false;
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const added = week?.weekIds?.has(Number(id)) ?? false;
  const [tags, setTags] = useState("");
  const [photoData, setPhotoData] = useState(null);
  const [photoLoading, setPhotoLoading] = useState(false);
  const [saveNotice, setSaveNotice] = useState("");
  const [name, setName] = useState("");
  const [servings, setServings] = useState(4);
  const [minutes, setMinutes] = useState("");
  const [ings, setIngs] = useState("");
  const [steps, setSteps] = useState([]);
  const [draftServings, setDraftServings] = useState(null);
  const [familyPortions, setFamilyPortions] = useState(null);
  const [showMore, setShowMore] = useState(false);
  // "Report a problem": null closed, { reason, note } while writing; reportedId once sent.
  const [report, setReport] = useState(null);
  const [reportedId, setReportedId] = useState(null);
  const moreRef = useRef(null);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 880px)");
    const apply = () => setDesktop(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("recipeSide", String(side));
    } catch {
      /* storage off */
    }
  }, [side]);

  useEffect(() => {
    if (!desktop || !recipe) return;
    const layout = layoutRef.current;
    if (!layout) return;
    const fit = () => {
      const width = layout.getBoundingClientRect().width;
      setSide((w) => Math.min(Math.max(SIDE_MIN, width - PHOTO_MIN), Math.max(SIDE_MIN, Math.round(w))));
    };
    fit();
    const obs = new ResizeObserver(fit);
    obs.observe(layout);
    return () => obs.disconnect();
  }, [desktop, recipe]);

  function clampSide(px) {
    const width = layoutRef.current?.getBoundingClientRect().width || px + PHOTO_MIN;
    return Math.min(Math.max(SIDE_MIN, width - PHOTO_MIN), Math.max(SIDE_MIN, Math.round(px)));
  }

  function startSplit(event) {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    const handle = event.currentTarget;
    handle.setPointerCapture(event.pointerId);
    const origin = event.clientX;
    const start = side;
    document.body.classList.add("is-resizing");
    const move = (ev) => setSide(clampSide(start + ev.clientX - origin));
    const stop = () => {
      document.body.classList.remove("is-resizing");
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", stop);
      handle.removeEventListener("pointercancel", stop);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", stop);
    handle.addEventListener("pointercancel", stop);
  }

  function nudgeSplit(event) {
    const step = event.shiftKey ? 48 : 24;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      setSide((w) => clampSide(w - step));
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      setSide((w) => clampSide(w + step));
    }
  }

  useEffect(() => {
    setEditing(false);
    setDraftServings(null);
    setFamilyPortions(null);
    let active = true;
    api.household().then((household) => {
      const portions = household.prefs?.family_portions;
      if (active && Number.isInteger(portions) && portions >= 1 && portions <= 50) setFamilyPortions(portions);
    }).catch(() => {});
    setShowMore(false);
    api.recipe(id).then(setRecipe).catch((e) => setErr(e.message));
    week?.load?.().catch((e) => setErr(e.message));
    return () => { active = false; };
  }, [id]);

  useEffect(() => {
    api.auth.status().then((s) => setAdmin(Boolean(s?.admin))).catch(() => setAdmin(false));
  }, []);

  useEffect(() => {
    if (!showMore) return undefined;
    function onDoc(e) {
      if (!moreRef.current?.contains(e.target)) setShowMore(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [showMore]);

  function resetDraft(value = recipe) {
    setPhotoData(null);
    setTags((value.tags || []).join(", "));
    setName(value.name);
    setServings(value.servings);
    setMinutes(value.cooking_minutes == null ? "" : String(value.cooking_minutes));
    setIngs(ingLines(value));
    setSteps(stepsFromRecipe(value.instructions));
    setSaveNotice("");
  }

  useEffect(() => {
    if (recipe && admin) resetDraft(recipe);
  }, [recipe?.id, admin]);

  function startEdit() {
    if (!canEdit) return;
    resetDraft();
    setEditing(true);
    setShowMore(false);
    setErr("");
  }

  async function selectPhoto(event) {
    const file = event.target.files?.[0];
    setPhotoData(null);
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5_000_000) {
      setErr("Choose a JPEG, PNG, or WebP photo under 5 MB.");
      event.target.value = "";
      return;
    }
    setPhotoLoading(true);
    setErr("");
    try {
      const data = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error("Couldn't read this photo."));
        reader.readAsDataURL(file);
      });
      setPhotoData(data);
    } catch (e) { setErr(e.message); }
    finally { setPhotoLoading(false); }
  }

  function editPayload() {
    return {
      ...(photoData ? { photo_data: photoData } : {}),
      tags: [...new Set(tags.split(",").map((tag) => tag.trim()).filter(Boolean))],
      name: name.trim(),
      servings: Number(servings) || 4,
      cooking_minutes: minutes === "" ? null : Number(minutes),
      ingredients: ings.split("\n").map(parseIngLine).filter(Boolean),
      instructions: serializeSteps(steps),
    };
  }

  async function saveEdit(e) {
    e.preventDefault();
    setErr("");
    setSaveNotice("");
    setBusy(true);
    try {
      const next = await api.patchRecipe(recipe.id, { in_place: true, ...editPayload() });
      setRecipe(next);
      resetDraft(next);
      setEditing(false);
      setSaveNotice("Changes saved.");
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

  async function deleteOwn() {
    setShowMore(false);
    if (!window.confirm(`Delete “${recipe.name}” from your recipes?`)) return;
    setBusy(true);
    try {
      await api.deleteRecipe(recipe.id);
      go("/recipes?list=mine");
    } catch (e) {
      setErr(e.message);
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

  // Admin: hide a catalog recipe from everyone, or bring it back. Nothing is deleted; plans that
  // already use it still open it.
  async function toggleRetired() {
    setShowMore(false);
    const on = !recipe.retired;
    if (on && !window.confirm(`Hide “${recipe.name}” from everyone’s recipe lists and suggestions? Existing plans keep it. You can show it again from Recipes to edit.`)) return;
    setBusy(true);
    try {
      setRecipe(await api.retireRecipe(recipe.id, on));
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function updateWorkflow(changes) {
    setBusy(true);
    setErr("");
    try { setRecipe(await api.recipeWorkflow(recipe.id, changes)); }
    catch (e) { setErr(e.message); }
    finally { setBusy(false); }
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
    if (busy) return;
    setBusy(true);
    try {
      const plan = await api.plan();
      const removing = plan.slots.some((slot) => slot.recipe_id === recipe.id);
      const slots = removing ? plan.slots.filter((slot) => slot.recipe_id !== recipe.id).map(asSlotIn) : [
        ...plan.slots.map(asSlotIn),
        { recipe_id: recipe.id, day_index: null, meal_type: "dinner", servings: draftServings ?? undefined },
      ];
      await api.putSlots(plan.id, slots);
      await week?.load?.();
      week?.toast?.(removing ? "Removed from this plan" : "Added to this plan");
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
    : (draftServings ?? familyPortions ?? recipe.servings ?? 4);

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

  function CookBlock({ headed = false }) {
    return (
      <>
        {headed ? <h3>Cook</h3> : null}
        {recipe.instructions_source === "dinnerdesk" && recipe.instructions_copied_from_third_party === false && <p className="muted">Instructions customized by Dinnerdesk</p>}
        {sourceHost(recipe.source_url) && !recipe.catalog && (
          <p className="muted">
            {recipe.instructions_source === "import" ? "Steps from " : "Original recipe: "}
            <a href={recipe.source_url} target="_blank" rel="noopener noreferrer">{sourceHost(recipe.source_url)}</a>
          </p>
        )}
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
              {/* Far-future feature: <StepTimers text={s.text || s.step || ""} /> */}
              {s.ings ? (
                <div className="step-ings">
                  <StepText text={amountLines(s.ings)} />
                </div>
              ) : null}
            </li>
          ))}
        </ol>
      </>
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
                  {!admin && !recipe.catalog ? (
                    <button type="button" role="menuitem" onClick={deleteOwn} disabled={busy}>
                      Delete recipe
                    </button>
                  ) : null}
                  {admin && recipe.catalog ? (
                    <button type="button" role="menuitem" onClick={toggleRetired} disabled={busy}>
                      {recipe.retired ? "Show to everyone" : "Hide from everyone"}
                    </button>
                  ) : null}
                  {admin && recipe.catalog && recipe.edited ? (
                    <button type="button" role="menuitem" onClick={restoreOriginal} disabled={busy || photoLoading}>
                      Restore original
                    </button>
                  ) : null}
                </div>
              )}
            </div>
          </div>
        )}
      </header>
      {!editing && <ReviewedBadge reviewed={recipe.reviewed} detail />}
      {!editing && admin && (
        <label className="recipe-review-control">
          <input type="checkbox" checked={Boolean(recipe.reviewed)} disabled={busy}
            onChange={async (e) => {
              const on = e.target.checked;
              setBusy(true);
              try { setRecipe(await api.reviewRecipe(recipe.id, on)); }
              catch (e) { setErr(e.message); }
              finally { setBusy(false); }
            }} /> Kitchen-tested
        </label>
      )}
      {!editing && (
        <div className="tabs">
          {["overview", "cook"].map((t) => (
            <button key={t} type="button" className={`tab-btn${tab === t ? " is-on" : ""}`} onClick={() => setTab(t)}>
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
          {canEdit && !admin && (
            <button type="button" className="tab-btn" onClick={startEdit}>
              Edit
            </button>
          )}
        </div>
      )}
      <div className="recipe-layout" ref={layoutRef}>
        {!editing && (
          <aside className={`recipe-side${both ? " is-both" : ""}`} style={desktop ? { width: side } : undefined}>
            <ServingsMeta />
            <div className="recipe-side-cols">
              <div>
                <h3>Ingredients</h3>
                <ul className="plain">
                  {recipe.ingredients.map((ing) => (
                    <li key={`${ing.ingredient_id}-${ing.name}`}>
                      {ing.quantity ? `${scaleAmount(ing.quantity, recipe.servings, mealServings)} ` : ""}
                      {ing.name}
                    </li>
                  ))}
                </ul>
              </div>
              {both && (
                <div>
                  <CookBlock headed />
                </div>
              )}
            </div>
          </aside>
        )}
        {!editing && desktop && (
          <div
            className="recipe-resizer"
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize ingredients and photo"
            aria-valuemin={SIDE_MIN}
            aria-valuenow={Math.round(side)}
            tabIndex={0}
            onPointerDown={startSplit}
            onKeyDown={nudgeSplit}
          />
        )}
        <div className="scroll pad recipe-body">
          {err && <p className="banner err">{err}</p>}
          {saveNotice && <p className="banner ok" role="status">{saveNotice}</p>}
          {recipe.retired && (
            <p className="banner" role="status">
              Removed from the app. Only plans that already use it can open it.
            </p>
          )}
              {admin && (
                <fieldset className="recipe-admin-actions" disabled={busy || photoLoading}>
                  <legend>Recipe management</legend>
                  <button type="button" onClick={() => updateWorkflow({ to_edit: !recipe.to_edit })}>
                    {recipe.to_edit ? "Remove To edit tag" : "Tag as To edit"}
                  </button>
                  {recipe.catalog && <button type="button" onClick={toggleRetired}>
                    {recipe.retired ? "Show to everyone" : "Hide from everyone"}
                  </button>}
                  <button type="button" onClick={() => updateWorkflow({ delete_requested: !recipe.delete_requested })}>
                    {recipe.delete_requested ? "Cancel deletion request" : "Delete — send for review"}
                  </button>
                  <p className="help">Deletion requests go to review; nothing is deleted. Hidden recipes stay in existing plans.</p>
                  <button type="button" onClick={() => go("/settings/recipe-flags")}>Open Recipes to edit</button>
                </fieldset>
              )}
          {admin && !editing && tab === "overview" && (
            <RecipeGallery recipe={recipe} canEdit={canEdit} onChange={setRecipe} />
          )}
          {(editing || (admin && tab === "overview")) && canEdit ? (
            <form id="recipe-edit" onSubmit={saveEdit}>
              <fieldset className="recipe-edit-fields" disabled={busy || photoLoading}>
              {editing && <>
              <label className="block-label" htmlFor="recipe-photo">Primary photo</label>
              <FoodPhoto path={recipe.photo_path} hideUnavailable />
              <input id="recipe-photo" type="file" accept="image/jpeg,image/png,image/webp" disabled={busy || photoLoading} onChange={selectPhoto} />
              <p className="help">Choose your own JPEG, PNG, or WebP photo under 5 MB. {recipe.catalog ? "Save updates the catalog photo for everyone. Save as copy uses it only on the new recipe." : "The photo is saved with this recipe."}</p>
              {photoData && <img src={photoData} alt="New recipe photo preview" style={{ width: "100%", maxWidth: 320, aspectRatio: "1", objectFit: "cover" }} />}
              </>}
              <label className="block-label" htmlFor="recipe-tags">Tags</label>
              <input id="recipe-tags" className="field" value={tags} onChange={(e) => setTags(e.target.value)} disabled={busy} placeholder="low carb pasta, quick dinner" />
              <p className="help">Separate tags with commas. {recipe.catalog ? "Save updates these tags for everyone. Save as copy changes only the new recipe." : "Tags apply to this kitchen recipe."}</p>
              <p className="help">Diet, allergy, and avoid filters use the recipe name and ingredients automatically. Tags such as “low carb pasta” are labels and do not change those filters.</p>
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
                    ? "Save updates this catalog recipe for everyone. Save as copy makes a new kitchen recipe and leaves the catalog dish alone."
                    : "Save updates this kitchen recipe."
                }
              />
              {admin && !editing && <div className="recipe-inline-actions">
                <button type="submit" className="btn-primary" disabled={busy || photoLoading}>{busy ? "Saving..." : "Save changes"}</button>
                <button type="button" className="btn-secondary" disabled={busy || photoLoading} onClick={() => resetDraft()}>Discard changes</button>
                {recipe.catalog && <button type="button" className="btn-secondary" disabled={busy || photoLoading} onClick={saveCopy}>Save as copy</button>}
              </div>}
              </fieldset>
            </form>
          ) : (
            <>
              {(tab === "overview" || both) && (
                <>
                  <RecipeGallery recipe={recipe} canEdit={canEdit} onChange={setRecipe} />
                  {tab === "overview" && <>
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

                  </>}
                </>
              )}
              {tab === "cook" && !both && <CookBlock />}
            </>
          )}
{admin && !editing && tab === "overview" && (<>
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
                  </>)}
          {recipe.catalog && !editing && (reportedId === recipe.id
            ? <p className="muted recipe-report-done" role="status">Thanks. We'll take a look at this recipe.</p>
            : report === null
              ? <button type="button" className="text-link recipe-report" onClick={() => setReport({ reason: "", note: "" })}>Report a problem with this recipe</button>
              : <form className="recipe-report-form" onSubmit={(e) => {
                  e.preventDefault();
                  if (!report.reason) return;
                  setBusy(true);
                  api.reportRecipe(recipe.id, report.reason, report.note.trim())
                    .then(() => { setReportedId(recipe.id); setReport(null); })
                    .catch((error) => setErr(error.message))
                    .finally(() => setBusy(false));
                }}>
                  <fieldset>
                    <legend>What's wrong?</legend>
                    {REPORT_REASONS.map(([key, label]) => (
                      <label key={key} className="recipe-report-reason">
                        <input type="radio" name="report-reason" value={key} checked={report.reason === key}
                          onChange={() => setReport({ ...report, reason: key })} />
                        {label}
                      </label>
                    ))}
                  </fieldset>
                  <label htmlFor="recipe-report-note">Anything to add? (optional)</label>
                  <textarea id="recipe-report-note" className="field" rows={3} maxLength={1000} value={report.note}
                    placeholder="e.g. Step 4 says to add the cream but it's not in the ingredients"
                    onChange={(e) => setReport({ ...report, note: e.target.value })} />
                  <div className="recipe-report-actions">
                    <button type="submit" className="btn-primary" disabled={busy || !report.reason}>Send report</button>
                    <button type="button" className="btn-secondary" disabled={busy} onClick={() => setReport(null)}>Cancel</button>
                  </div>
                </form>)}
        </div>
      </div>
      <footer className="dock">
        {editing && canEdit ? (
          <>
            <button type="submit" form="recipe-edit" className="btn-primary block" disabled={busy || photoLoading}>
              {busy ? "Saving…" : "Save"}
            </button>
            {recipe.catalog ? (
              <button type="button" className="btn-secondary block" disabled={busy || photoLoading} onClick={saveCopy}>
                Save as copy
              </button>
            ) : null}
          </>
        ) : (
          <button type="button" className="btn-primary block" disabled={busy || photoLoading} onClick={addToWeek}>
            {busy ? "Updating…" : added ? "Remove from this plan" : "Add to this plan"}
          </button>
        )}
      </footer>
    </section>
  );
}
