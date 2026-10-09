/** Arrow-key movement for a search box and the results under it (#19).
 *  ↓ from the box goes to the first result; ↓ / ↑ move between results; ↑ from the first
 *  result, or Escape, goes back to the box. Enter and Space work because results are buttons,
 *  and Tab still walks everything in order. Put the handler on an element that holds both. */
export function onListKeys(e, itemSelector, boxSelector = "input") {
  if (!["ArrowDown", "ArrowUp", "Escape"].includes(e.key)) return;
  const root = e.currentTarget;
  const box = root.querySelector(boxSelector);
  const items = [...root.querySelectorAll(itemSelector)].filter((el) => !el.disabled);
  const at = items.indexOf(document.activeElement);
  const inBox = document.activeElement === box;
  if (e.key === "Escape") {
    if (at >= 0 && box) { e.preventDefault(); box.focus(); }
    return;
  }
  if (!items.length || (!inBox && at < 0)) return;
  e.preventDefault();
  if (e.key === "ArrowDown") items[inBox ? 0 : Math.min(at + 1, items.length - 1)].focus();
  else if (at <= 0) box?.focus();
  else items[at - 1].focus();
}
