import { useEffect, useRef, useState } from "react";
import FoodPhoto from "./FoodPhoto.jsx";
import { api } from "./api.js";
import { Tip } from "./Tip.jsx";

export function RecipeGallery({ recipe, canEdit, onChange }) {
  const photos = recipe.photos ?? (recipe.photo_path ? [{ path: recipe.photo_path, primary: true, ai: recipe.photo_ai, shared: recipe.photo_shared }] : []);
  const [active, setActive] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const track = useRef(null);
  const photo = photos[active];

  useEffect(() => {
    setActive(0);
    track.current?.scrollTo({ left: 0 });
  }, [recipe.id, recipe.photo_path]);

  function show(index) {
    setActive(index);
    const el = track.current;
    if (el) el.scrollTo({ left: el.clientWidth * index, behavior: "smooth" });
  }

  async function addPhotos(event) {
    const input = event.target;
    const files = Array.from(input.files || []);
    if (!files.length) return;
    if (files.some(file => !["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5_000_000)) {
      setError("Choose JPEG, PNG, or WebP photos under 5 MB each.");
      input.value = "";
      return;
    }
    setBusy(true);
    setError("");
    let saved = 0;
    try {
      for (const file of files) {
        setNotice(`Adding photo ${saved + 1} of ${files.length}…`);
        const data = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.onerror = () => reject(new Error("Couldn't read this photo."));
          reader.readAsDataURL(file);
        });
        onChange(await api.addRecipePhoto(recipe.id, data));
        saved += 1;
      }
      setNotice(`${saved} ${saved === 1 ? "photo added" : "photos added"}.`);
    } catch (e) {
      setNotice(saved ? `${saved} ${saved === 1 ? "photo was" : "photos were"} added.` : "");
      setError(`${e.message} Select the remaining photos to try again.`);
    } finally {
      setBusy(false);
      input.value = "";
    }
  }

  async function primary() {
    setBusy(true);
    setError("");
    try {
      onChange(await api.setRecipePrimaryPhoto(recipe.id, photo.path));
      setNotice("Primary photo saved.");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return (
    <section className="recipe-gallery" aria-label="Recipe photos">
      {photos.length > 0 && <>
        <div className="recipe-gallery-track" ref={track} onScroll={event => {
          const el = event.currentTarget;
          if (el.clientWidth) setActive(Math.max(0, Math.min(photos.length - 1, Math.round(el.scrollLeft / el.clientWidth))));
        }}>
          {photos.map((item, index) => <div className="recipe-gallery-slide" key={item.path} role="group" aria-label={`Photo ${index + 1} of ${photos.length}`}>
            <FoodPhoto className="hero" path={item.path} alt={`${recipe.name}, photo ${index + 1}`} />
            <PhotoCredit photo={item} />
          </div>)}
        </div>
        <div className="recipe-gallery-controls">
          {photos.length > 1 && <button type="button" disabled={active === 0} onClick={() => show(active - 1)} aria-label="Previous photo">←</button>}
          <span aria-live="polite">{active + 1} / {photos.length}{photo?.primary ? " · Primary" : ""}</span>
          {photos.length > 1 && <button type="button" disabled={active === photos.length - 1} onClick={() => show(active + 1)} aria-label="Next photo">→</button>}
          {canEdit && photo && !photo.primary && <button type="button" className="text-link" disabled={busy} onClick={primary}>Make primary</button>}
        </div>
        {photo?.ai && <Tip id="recipes.ai-photo" className="ai-photo-tip">This photo was made with AI. It shows the kind of dish, not this exact recipe.</Tip>}
        {!photo?.ai && photo?.shared && <Tip id="recipes.shared-photo" className="ai-photo-tip">This photo is from a similar recipe, so it may not match this one exactly.</Tip>}
      </>}
      {canEdit && <div>
        <label className="text-link" htmlFor={`add-recipe-photos-${recipe.id}`}>Add photos</label>
        <input id={`add-recipe-photos-${recipe.id}`} type="file" multiple accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={addPhotos} />
        <p className="help">Add your own photos, up to 5 MB each. The primary photo appears on recipe cards.{recipe.catalog ? " Changes to this catalog gallery are shared with everyone." : " Photos are saved with this recipe."}</p>
      </div>}
      {notice && <p role="status">{notice}</p>}
      {error && <p className="banner err" role="alert">{error}</p>}
    </section>
  );
}


function PhotoCredit({ photo }) {
  const [open, setOpen] = useState(false);
  const id = `photo-credit-${photo.path.replace(/[^a-z0-9]/gi, "-")}`;
  const label = photo.credit || "Photo source not recorded";
  return <span className="photo-credit" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
    onFocus={() => setOpen(true)} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}
    onKeyDown={event => { if (event.key === "Escape") setOpen(false); }}>
    <button type="button" className="photo-credit-icon" aria-label="Photo source" aria-expanded={open} aria-controls={id}
      onClick={() => setOpen(true)}>ⓘ</button>
    {open && <span id={id} className="photo-credit-tooltip" role="note">
      {label}
      {photo.source_url && <a href={photo.source_url} target="_blank" rel="noopener noreferrer">View source ↗</a>}
    </span>}
  </span>;
}
