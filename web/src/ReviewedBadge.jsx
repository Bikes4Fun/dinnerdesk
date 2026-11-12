import { useRef } from "react";
import { Copy } from "./Copy.js";

export function TestedSeal() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m12 2 3 2 3.5.5.5 3.5 2 4-2 3-.5 3.5-3.5.5-3 2-3-2-3.5-.5L5 15l-2-3 2-4 .5-3.5L9 4Z" /><path d="m8 12 3 3 5-6" /></svg>;
}

export function ReviewedBadge({ reviewed, detail = false }) {
  const dialog = useRef(null);
  if (!reviewed) return null;
  const label = <><TestedSeal />{Copy.text("recipe.reviewed")}</>;
  if (!detail) return <span className="kitchen-tested" aria-label={Copy.text("recipe.reviewed.description")}>{label}</span>;
  return <>
    <button type="button" className="kitchen-tested-chip" aria-haspopup="dialog" onClick={() => dialog.current.showModal()}>{label}<span aria-hidden="true">›</span></button>
    <dialog ref={dialog} className="kitchen-tested-sheet" aria-label={Copy.text("recipe.reviewed")} onClick={e => { if (e.target === e.currentTarget) e.currentTarget.close(); }}>
      <h2 className="kitchen-tested"><TestedSeal />{Copy.text("recipe.reviewed")}</h2>
      <p>{Copy.text("recipe.kitchen-tested.explanation")}</p>
      <button type="button" className="btn-primary block" onClick={() => dialog.current.close()}>Got it</button>
    </dialog>
  </>;
}

export function RecipeStatusLine({ recipe }) {
  return <span className="recipe-status-line">
    {recipe.cooking_minutes ? <span>{recipe.cooking_minutes} min</span> : null}
    {recipe.cooking_minutes && recipe.reviewed ? <span aria-hidden="true">·</span> : null}
    <ReviewedBadge reviewed={recipe.reviewed} />
  </span>;
}
