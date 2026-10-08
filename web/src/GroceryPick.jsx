import { useEffect, useState } from "react";
import { api } from "./api.js";

export function GroceryPick({
  value,
  onChange,
  onPick,
  placeholder = "Search items…",
  autoFocus = false,
  inputClass = "field-input",
}) {
  const [items, setItems] = useState([]);
  const [custom, setCustom] = useState("");
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const q = (value || "").trim();

  useEffect(() => {
    if (!q) {
      setItems([]);
      setCustom("");
      setNote("");
      setErr("");
      return;
    }
    const t = setTimeout(() => {
      api
        .groceryItems(value, 12)
        .then((d) => {
          setItems(d.items || []);
          setCustom(d.custom || "");
          setNote(d.note || "");
          setErr("");
        })
        .catch((e) => {
          setItems([]);
          setCustom(q);
          setNote("");
          setErr(e.message || "Search failed");
        });
    }, 80);
    return () => clearTimeout(t);
  }, [value, q]);

  function pick(name) {
    onChange(name);
    if (onPick) onPick(name);
  }

  const show = q.length > 0 && (items.length > 0 || custom || err);

  return (
    <div className="grocery-pick">
      <input
        className={inputClass}
        value={value}
        autoFocus={autoFocus}
        placeholder={placeholder}
        autoComplete="off"
        onChange={(e) => onChange(e.target.value)}
      />
      {show ? (
        <div className="grocery-pick-list">
          {err ? <p className="search-note">{err}</p> : null}
          {!err && note === "ideas" ? (
            <p className="search-note">No exact match. Closest items:</p>
          ) : null}
          {!err && note === "closest" ? (
            <p className="search-note">No item used every word. Closest matches:</p>
          ) : null}
          {items.map((it) => (
            <button type="button" key={it.name} className="grocery-pick-hit" onClick={() => pick(it.name)}>
              {it.name}
            </button>
          ))}
          {custom ? (
            <button type="button" className="grocery-pick-hit is-custom" onClick={() => pick(custom)}>
              Add “{custom}”
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
