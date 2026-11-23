import { useState } from "react";
import { api, photoSrc } from "../api.js";
import { go } from "../nav.js";
import { parseIngLine } from "../parseIngredient.js";
import { RecipeEditorFields, emptyStep, serializeSteps, stepsFromRecipe } from "../RecipeEditor.jsx";
import { Copy } from "../Copy.js";

function fromUrlMode() {
  return new URLSearchParams(window.location.search).get("from") === "url";
}

export function NewRecipe() {
  const byUrl = fromUrlMode();
  const [name, setName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [servings, setServings] = useState(4);
  const [minutes, setMinutes] = useState("");
  const [ings, setIngs] = useState(byUrl ? "" : "1 onion\n2 cloves garlic");
  const [steps, setSteps] = useState([emptyStep()]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  // URL mode: the form shows once the page is read, or once the cook chooses to type it in.
  const [importing, setImporting] = useState(false);
  const [imported, setImported] = useState(false);
  const [showForm, setShowForm] = useState(!byUrl);
  // The imported page's photo (copied for this kitchen on save), or the cook's own.
  const [siteImage, setSiteImage] = useState("");
  const [ownPhoto, setOwnPhoto] = useState(null);

  async function chooseOwnPhoto(event) {
    const file = event.target.files?.[0];
    setOwnPhoto(null);
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5_000_000) {
      setErr("Choose a JPEG, PNG, or WebP photo under 5 MB.");
      event.target.value = "";
      return;
    }
    try {
      setOwnPhoto(
        await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.onerror = () => reject(new Error("Couldn't read this photo."));
          reader.readAsDataURL(file);
        }),
      );
      setErr("");
    } catch (e) {
      setErr(e.message);
    }
  }

  async function onImport() {
    const url = sourceUrl.trim();
    if (!url) return;
    setImporting(true);
    setErr("");
    try {
      const draft = await api.importRecipe(url);
      setName(draft.name || "");
      setServings(draft.servings || 4);
      setMinutes(draft.cooking_minutes == null ? "" : String(draft.cooking_minutes));
      setIngs((draft.ingredient_lines || []).join("\n"));
      const read = stepsFromRecipe(draft.instructions);
      setSteps(read.length ? read : [emptyStep()]);
      setSourceUrl(draft.source_url || url);
      setSiteImage(draft.image_url || "");
      setImported(true);
      setShowForm(true);
    } catch (e) {
      setErr(e.message);
    } finally {
      setImporting(false);
    }
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!showForm) {
      onImport();
      return;
    }
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
        tags: [byUrl ? "imported" : "custom"],
        imported,
        photo_url: imported ? siteImage : "",
        ...(ownPhoto ? { photo_data: ownPhoto } : {}),
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
        <h1>{byUrl ? Copy.text("ui.import.a.recipe") : Copy.text("ui.new.recipe")}</h1>
      </header>
      <form className="scroll pad" onSubmit={onSubmit}>
        {err && <p className="banner err" role="alert">{err}</p>}
        {byUrl && (
          <>
            <label className="block-label" htmlFor="recipe-url">{Copy.text("ui.recipe.page")}</label>
            <input
              id="recipe-url"
              className="field"
              type="url"
              required={!showForm}
              placeholder="https://"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
            />
            <button type="button" className="btn-secondary" disabled={importing || !sourceUrl.trim()} onClick={onImport}>
              {importing ? "Reading…" : imported ? Copy.text("ui.read.again") : "Import"}
            </button>
            {imported ? (
              <p className="help">{Copy.text("ui.check.it.over.before.you")}</p>
            ) : !showForm ? (
              <p className="help">
                Paste a link to a recipe on a public website.{" "}
                <button type="button" className="text-link" onClick={() => setShowForm(true)}>
                  Type it in instead
                </button>
              </p>
            ) : null}
          </>
        )}
        {showForm && (
          <>
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
              help="Saved to your kitchen only. Find it under Your Recipes."
            />
            {!byUrl && (
              <>
                <label className="block-label" htmlFor="recipe-source">Source (optional)</label>
                <input
                  id="recipe-source"
                  className="field"
                  type="url"
                  placeholder="https:// where this recipe came from"
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                />
              </>
            )}
            <label className="block-label" htmlFor="recipe-photo">Photo</label>
            {ownPhoto || (imported && siteImage) ? (
              <span className="food-photo" style={{ aspectRatio: "1 / 1", height: "auto", maxWidth: 220 }}>
                <img src={ownPhoto || photoSrc(siteImage)} alt="" onError={(e) => { e.currentTarget.style.visibility = "hidden"; }} />
              </span>
            ) : null}
            <input id="recipe-photo" type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseOwnPhoto} />
            <p className="help">
              {ownPhoto
                ? "Your photo will be used."
                : imported && siteImage
                  ? Copy.text("ui.this.is.the.photo.from")
                  : Copy.text("ui.add.a.photo.you.took")}
            </p>
            <button type="submit" className="btn-primary block" disabled={busy || importing}>
              {busy ? "Saving…" : "Save recipe"}
            </button>
          </>
        )}
      </form>
    </section>
  );
}
