import { useEffect, useMemo, useState } from "react";
import { GroceryPick } from "../GroceryPick.jsx";
import { api, photoSrc } from "../api.js";
import { go } from "../nav.js";

const DEFAULT_STORES = [
  { id: "costco", name: "Costco" },
  { id: "walmart", name: "Walmart" },
  { id: "local", name: "Local grocer" },
  { id: "farmers", name: "Farmers market" },
];
const DEFAULT_AISLES = [
  { id: "produce", name: "Produce", number: "" },
  { id: "dairy", name: "Dairy, Cheese & Eggs", number: "" },
  { id: "meat", name: "Meat & Seafood", number: "" },
  { id: "pantry", name: "Pantry", number: "" },
  { id: "other", name: "Other", number: "" },
];
const GROCERY_EMOJI = [
  ["avocado", "🥑"],
  ["tomato", "🍅"],
  ["greens", "🥬"],
  ["lettuce", "🥬"],
  ["spinach", "🥬"],
  ["kale", "🥬"],
  ["rosemary", "🌿"],
  ["cilantro", "🌿"],
  ["basil", "🌿"],
  ["herb", "🌿"],
  ["potato", "🥔"],
  ["chicken", "🍗"],
  ["steak", "🥩"],
  ["beef", "🥩"],
  ["pork", "🥓"],
  ["shrimp", "🦐"],
  ["salmon", "🐟"],
  ["fish", "🐟"],
  ["oil", "🫒"],
  ["olive", "🫒"],
  ["lime", "🍋"],
  ["lemon", "🍋"],
  ["rice", "🍚"],
  ["bean", "🫘"],
  ["onion", "🧅"],
  ["garlic", "🧄"],
  ["pepper", "🫑"],
  ["corn", "🌽"],
  ["carrot", "🥕"],
  ["broccoli", "🥦"],
  ["egg", "🥚"],
  ["cheese", "🧀"],
  ["milk", "🥛"],
  ["bread", "🍞"],
  ["tortilla", "🌮"],
  ["pasta", "🍝"],
  ["mushroom", "🍄"],
  ["apple", "🍎"],
  ["banana", "🍌"],
];

function groceryEmoji(name) {
  const n = (name || "").toLowerCase();
  return GROCERY_EMOJI.find(([key]) => n.includes(key))?.[1] || "";
}

function shortMealName(name) {
  const raw = String(name || "").trim();
  if (!raw) return "";
  const head = raw.split(",")[0].trim().split(/\s+with\s+/i)[0].trim();
  return head || raw;
}

function slug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "store";
}

function storeOf(stores, id) {
  return stores.find((s) => s.id === id);
}

export function Grocery() {
  const [view, setView] = useState("list");
  const [itemId, setItemId] = useState(null);
  const [planId, setPlanId] = useState(null);
  const [lines, setLines] = useState([]);
  const [stores, setStores] = useState(DEFAULT_STORES);
  const [aisles, setAisles] = useState(DEFAULT_AISLES);
  const [groupByStore, setGroupByStore] = useState(false);
  const [storeFilter, setStoreFilter] = useState("all");
  const [showMeals, setShowMeals] = useState(false);
  const [showAisleNums, setShowAisleNums] = useState(false);
  const [showEmoji, setShowEmoji] = useState(false);
  const [menuStatus, setMenuStatus] = useState("");
  const [hideChecked, setHideChecked] = useState(true);
  const [sheet, setSheet] = useState(false);
  const [adding, setAdding] = useState(false);
  const [addName, setAddName] = useState("");
  const [newStore, setNewStore] = useState("");
  const [err, setErr] = useState("");

  function groceryPrefs() {
    return {
      stores,
      aisles,
      groupByStore,
      showMeals,
      showAisleNums,
      showEmoji,
      hideChecked,
    };
  }

  async function persist(next) {
    try {
      await api.putHousehold({ prefs: { grocery: { ...groceryPrefs(), ...next } } });
    } catch (e) {
      setErr(e.message);
    }
  }

  async function load() {
    const [plan, hh] = await Promise.all([api.plan(), api.household()]);
    const data = await api.rebuildGrocery(plan.id);
    setPlanId(plan.id);
    setLines(data.lines);
    const g = hh.prefs?.grocery || {};
    if (Array.isArray(g.stores)) setStores(g.stores);
    if (Array.isArray(g.aisles)) setAisles(g.aisles);
    if (typeof g.groupByStore === "boolean") setGroupByStore(g.groupByStore);
    if (typeof g.showMeals === "boolean") setShowMeals(g.showMeals);
    if (typeof g.showAisleNums === "boolean") setShowAisleNums(g.showAisleNums);
    if (typeof g.showEmoji === "boolean") setShowEmoji(g.showEmoji);
    if (typeof g.hideChecked === "boolean") setHideChecked(g.hideChecked);
  }

  useEffect(() => {
    load().catch((e) => setErr(e.message));
  }, []);

  async function patchLine(id, body) {
    setLines((cur) => cur.map((l) => (l.id === id ? { ...l, ...body, name: body.custom_text ?? l.name } : l)));
    try {
      await api.patchGrocery(id, body);
      if (Object.hasOwn(body, "custom_text")) await load();
    } catch (e) {
      setErr(e.message);
      load();
    }
  }

  async function addLine(e) {
    e.preventDefault();
    const names = addName.split(",").map((n) => n.trim()).filter(Boolean);
    if (!planId || !names.length) return;
    const store = storeFilter === "all" ? "" : storeFilter;
    try {
      const added = [];
      for (const name of names) {
        added.push(await api.addGroceryLine(planId, { name, store }));
      }
      setLines((cur) => [...cur.filter((line) => !added.some((next) => next.id === line.id)), ...new Map(added.map((line) => [line.id, line])).values()]);
      setAddName("");
    } catch (e) {
      setErr(e.message);
    }
  }

  async function uncheckAll() {
    const ids = lines.filter((l) => l.checked && !l.never_shop).map((l) => l.id);
    setLines((cur) => cur.map((l) => (ids.includes(l.id) ? { ...l, checked: false } : l)));
    try {
      await Promise.all(ids.map((id) => api.patchGrocery(id, { checked: false })));
      setMenuStatus("Items unchecked");
    } catch (e) {
      setErr(e.message);
      load();
    }
  }

  /** What's left to buy, grouped by aisle in store order, for the selected store. */
  function shareText() {
    const left = lines.filter((l) => !l.checked && !l.never_shop && !l.from_pantry
      && (storeFilter === "all" || l.store === storeFilter));
    const store = stores.find((s) => s.id === storeFilter);
    const title = store ? `Grocery list — ${store.name}` : "Grocery list";
    if (!left.length) return `${title}\n\nNothing left to buy.`;
    const known = new Set(aisles.map((a) => a.id));
    const blocks = [...aisles.map((a) => [a.name, left.filter((l) => l.aisle === a.id)]),
      ["Other", left.filter((l) => !known.has(l.aisle))]].filter(([, rows]) => rows.length);
    const body = blocks.map(([name, rows]) =>
      `${name.toUpperCase()}\n${rows.map((l) => `• ${[l.quantity, l.name].filter(Boolean).join(" ")}`).join("\n")}`);
    return `${title}\n\n${body.join("\n\n")}`;
  }

  async function shareList() {
    const text = shareText();
    try {
      if (navigator.share) {
        await navigator.share({ title: "Grocery list", text });
        setSheet(false);
        return;
      }
      await navigator.clipboard.writeText(text);
      setMenuStatus("List copied. Paste it anywhere.");
    } catch (e) {
      if (e.name !== "AbortError") setErr(e.message);
    }
  }

  function emailList() {
    window.location.href = `mailto:?subject=${encodeURIComponent("Grocery list")}&body=${encodeURIComponent(shareText())}`;
    setSheet(false);
  }

  async function markAllComplete() {
    await Promise.all(lines.filter((line) => !line.checked).map((line) => api.patchGrocery(line.id, { checked: true })));
    await load();
    setMenuStatus("All items completed");
  }

  const visible = useMemo(() => {
    return lines.filter((l) => {
      if (l.never_shop) return false;
      if (hideChecked && l.checked) return false;
      const sid = l.store;
      if (groupByStore && storeFilter !== "all" && sid !== storeFilter) return false;
      return true;
    });
  }, [lines, hideChecked, groupByStore, storeFilter]);

  const checkedN = lines.filter((l) => l.checked && !l.never_shop).length;
  const remaining = lines.filter((l) => !l.checked && !l.never_shop).length;
  const item = lines.find((l) => l.id === itemId);

  function aisleBlocks(items) {
    const known = new Set(aisles.map((a) => a.id));
    const blocks = aisles.map((a) => ({
      ...a,
      rows: items.filter((g) => (g.aisle || "other") === a.id),
    }));
    const extra = items.filter((g) => !known.has(g.aisle || "other"));
    if (extra.length) blocks.push({ id: "extra", name: "Other", number: "", rows: extra });
    return blocks.filter((b) => b.rows.length);
  }

  function renderAisles(items) {
    return aisleBlocks(items).map((a) => (
      <section key={a.id} className="aisle-block">
        <div className="aisle-label">
          {a.name}
          {showAisleNums && a.number ? ` · Aisle ${a.number}` : ""}
        </div>
        {a.rows.map((line) => (
          <GroceryRow
            key={line.id}
            line={line}
            showMeals={showMeals}
            showEmoji={showEmoji}
            onCheck={() => patchLine(line.id, { checked: !line.checked })}
            onOpen={() => {
              setItemId(line.id);
              setView("item");
            }}
          />
        ))}
      </section>
    ));
  }

  if (view === "item" && item) {
    return (
      <ItemView
        item={item}
        stores={stores}
        aisles={aisles}
        err={err}
        onBack={() => setView("list")}
        onPatch={(body) => patchLine(item.id, body)}
        onFlags={async (flags) => {
          await api.upsertPantry({ name: item.name, have: item.from_pantry, never_shop: item.never_shop, ...flags });
          await load();
        }}
        onSubstitute={async (name) => {
          await api.addOverride({ from_name: item.name, to_name: name });
          await load();
          setView("list");
        }}
      />
    );
  }

  if (view === "stores") {
    return (
      <StoresView
        stores={stores}
        lines={lines}
        newStore={newStore}
        setNewStore={setNewStore}
        err={err}
        onBack={() => setView("list")}
        onAisles={() => setView("aisles")}
        onAssign={(id, store) => patchLine(id, { store })}
        onAdd={() => {
          const name = newStore.trim();
          if (!name) return;
          const id = slug(name);
          if (stores.some((s) => s.id === id)) return;
          const next = [...stores, { id, name }];
          setStores(next);
          setNewStore("");
          persist({ stores: next });
        }}
        onRemove={(id) => {
          const next = stores.filter((s) => s.id !== id);
          setStores(next);
          setLines((rows) => rows.map((line) => line.store === id ? { ...line, store: "" } : line));
          persist({ stores: next });
        }}
      />
    );
  }

  if (view === "aisles") {
    return (
      <AislesView
        aisles={aisles}
        lines={lines}
        err={err}
        onBack={() => setView("list")}
        onAssign={(id, aisle) => patchLine(id, { aisle })}
        onChange={(next) => {
          setAisles(next);
          persist({ aisles: next });
        }}
      />
    );
  }

  const storeOrder = storeFilter === "all" ? [...stores.map((s) => s.id), ""] : [storeFilter];
  const grouped = storeOrder.map((sid) => ({
    sid,
    name: storeOf(stores, sid)?.name || "Unassigned",
    items: visible.filter((g) => g.store === sid),
  }));

  return (
    <section className="screen">
      <header className="top">
        <h1>Grocery</h1>
        <div className="top-actions">
          <span className="count-pill">{remaining ? `${remaining} to buy` : "List clear"}</span>
          <button type="button" className="icon-btn" onClick={() => setSheet((v) => !v)} aria-label="More">
            ⋯
          </button>
        </div>
      </header>
      <div className="scroll pad grocery">
        {err && <p className="banner err">{err}</p>}
        <div className="chip-row flush-chips">
          <button
            type="button"
            className={`chip${groupByStore ? " is-on" : ""}`}
            onClick={() => {
              const next = !groupByStore;
              setGroupByStore(next);
              if (!next) setStoreFilter("all");
              persist({ groupByStore: next });
            }}
          >
            {groupByStore ? "Hide stores" : "All stores"}
          </button>
          <button
            type="button"
            className={`chip${showMeals ? " is-on" : ""}`}
            onClick={() => {
              const next = !showMeals;
              setShowMeals(next);
              persist({ showMeals: next });
            }}
          >
            {showMeals ? "Hide meals under items" : "Show meals under items"}
          </button>
          {groupByStore &&
            stores.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`chip${storeFilter === s.id ? " is-on" : ""}`}
                onClick={() => setStoreFilter((cur) => (cur === s.id ? "all" : s.id))}
              >
                {s.name}
              </button>
            ))}
        </div>

        {adding && (
          <form className="add-line" onSubmit={addLine}>
            <GroceryPick
              value={addName}
              onChange={setAddName}
              placeholder="Search items…"
              autoFocus
              inputClass="field"
            />
            <button type="submit" className="btn-secondary">
              Add
            </button>
          </form>
        )}

        {lines.length === 0 ? (
          <p className="help" data-tip="grocery.empty">Add meals on Plan and they show up here.</p>
        ) : groupByStore ? (
          grouped.map((block) =>
            block.items.length ? (
              <div key={block.sid}>
                {storeFilter === "all" && <div className="store-head">{block.name}</div>}
                {renderAisles(block.items)}
              </div>
            ) : null,
          )
        ) : (
          renderAisles(visible)
        )}

        {checkedN > 0 || !hideChecked ? (
          <button
            type="button"
            className="list-foot-link"
            onClick={() => {
              const next = !hideChecked;
              setHideChecked(next);
              persist({ hideChecked: next });
            }}
          >
            {hideChecked ? `Show checked${checkedN ? ` (${checkedN})` : ""}` : "Hide checked"}
          </button>
        ) : null}
      </div>

      <button
        type="button"
        className="fab"
        aria-label="Add item"
        onClick={() => {
          setAdding((v) => !v);
          setSheet(false);
        }}
      >
        +
      </button>

      {sheet && (
        <div className="action-sheet grocery-options">
          <label>Show completed items <input type="checkbox" checked={!hideChecked} onChange={(e) => { const value = !e.target.checked; setHideChecked(value); persist({ hideChecked: value }); }} /></label>
          <label>Show store groups <input type="checkbox" checked={groupByStore} onChange={(e) => { const value = e.target.checked; setGroupByStore(value); if (!value) setStoreFilter("all"); persist({ groupByStore: value }); }} /></label>
          <label>Show aisle numbers <input type="checkbox" checked={showAisleNums} onChange={(e) => { const value = e.target.checked; setShowAisleNums(value); persist({ showAisleNums: value }); }} /></label>
          <label>Show meals under each item <input type="checkbox" checked={showMeals} onChange={(e) => { const value = e.target.checked; setShowMeals(value); persist({ showMeals: value }); }} /></label>
          <label>Show emoji <input type="checkbox" checked={showEmoji} onChange={(e) => { const value = e.target.checked; setShowEmoji(value); persist({ showEmoji: value }); }} /></label>
          <button type="button" onClick={markAllComplete}>Complete all</button>
          <button type="button" onClick={uncheckAll}>Uncheck all</button>
          {menuStatus && <p className="grocery-action-status" role="status">{menuStatus}</p>}
          <button type="button" onClick={() => { setSheet(false); setView("stores"); }}>Edit stores</button>
          <button type="button" onClick={() => { setSheet(false); setView("aisles"); }}>Edit aisles</button>
          <button type="button" onClick={shareList}>Share list</button>
          <button type="button" onClick={emailList}>Email list</button>
          <button type="button" onClick={() => { setSheet(false); window.print(); }}>Print</button>
          <button type="button" onClick={() => setSheet(false)}>Done</button>
        </div>
      )}
    </section>
  );
}

function GroceryRow({ line, showMeals, showEmoji, onCheck, onOpen }) {
  const note = [];
  if (showMeals && line.used_by?.length) {
    note.push(line.used_by.map(shortMealName).filter(Boolean).join(" · "));
  }
  if (line.never_shop) note.push("Always checked off");

  return (
    <div
      className={`g-item${line.checked ? " is-done" : ""}${line.from_pantry ? " owned" : ""}${showEmoji ? " has-emo" : ""}${line.ingredient_photo_path ? " has-photo" : ""}`}
      onClick={onOpen}
    >
      <button type="button" className={`check${line.checked ? " on" : ""}`} aria-pressed={line.checked} aria-label={`${line.checked ? "Uncheck" : "Check off"} ${line.name}`} onClick={(e) => { e.stopPropagation(); onCheck(); }}>
        {line.checked ? "✓" : ""}
      </button>
      {showEmoji ? <span className="g-emo">{groceryEmoji(line.name)}</span> : null}
      {line.ingredient_photo_path ? (
        <img className="g-thumb" src={photoSrc(line.ingredient_photo_path)} alt="" />
      ) : null}
      <button type="button" className="g-main" onClick={(e) => { e.stopPropagation(); onOpen(); }}>
        <span className="g-name">{line.name}</span>
        {note.length > 0 && <span className="g-sub">{note.join(" · ")}</span>}
        {line.from_pantry && !line.never_shop && <span className="g-tip" data-tip="grocery.pantry"><span className="g-tip-star" aria-hidden="true">★</span> In your pantry, so it starts checked off</span>}
      </button>
      <span className="g-qty">{line.quantity}</span>
    </div>
  );
}

function ItemView({ item, stores, aisles, err, onBack, onPatch, onFlags, onSubstitute }) {
  const [name, setName] = useState(item.name);
  const [substitute, setSubstitute] = useState("");
  const [qty, setQty] = useState(item.quantity || "");
  useEffect(() => {
    setQty(item.quantity || "");
  }, [item.id, item.quantity]);

  return (
    <section className="screen">
      <header className="top sub">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Back">
          ←
        </button>
        <h1>Groceries</h1>
      </header>
      <div className="scroll pad grocery-editor">
        {err && <p className="banner err">{err}</p>}
        <input aria-label="Item name" id="grocery-item-name" className="grocery-name-edit" value={name} onChange={(e) => setName(e.target.value)} onBlur={() => { if (name.trim() && name !== item.name) onPatch({ custom_text: name.trim() }); }} />
        <p className="grocery-category">{aisles.find((a) => a.id === item.aisle)?.name || item.aisle}</p>
        <label className="grocery-amount-row" htmlFor="grocery-item-amount">Quantity
          <input id="grocery-item-amount" aria-label="Quantity" value={qty} onChange={(e) => setQty(e.target.value)} onBlur={() => onPatch({ quantity: qty })} />
        </label>
        <div className="ingredient-banner" aria-label={item.ingredient_photo_path ? undefined : "Ingredient photo space"}>
          {item.ingredient_photo_path && <img src={photoSrc(item.ingredient_photo_path)} alt={item.name} onError={() => { throw new Error(`Ingredient photo failed: ${item.name}`); }} />}
        </div>
        <label className="grocery-substitute-row">Substitute
          <input className="field" placeholder="Try another item" value={substitute} onChange={(e) => setSubstitute(e.target.value)} />
        </label>
        {substitute.trim() && <button className="text-link" onClick={() => onSubstitute(substitute.trim())}>Use this instead</button>}
        <h3 className="block-label">You'll use this in</h3>
        {item.used_in?.length ? (
          <>
            {item.used_in.map((meal) => (
              <button
                key={meal.id || meal.name}
                type="button"
                className="g-meal"
                onClick={() => meal.id && go(`/recipes/${meal.id}`)}
              >
                {meal.photo_path ? (
                  <img src={photoSrc(meal.photo_path)} alt="" />
                ) : (
                  <span className="ph" />
                )}
                <span>
                  <strong>{meal.name}</strong>
                  {meal.cooking_minutes ? <em>{meal.cooking_minutes} min</em> : null}
                </span>
              </button>
            ))}
          </>
        ) : item.used_by?.length ? (
          <ul className="plain">
            {item.used_by.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">Added by you</p>
        )}
        <div className="grocery-item-settings">
        <label className="toggle-row">Store <select className="field" value={item.store || ""} onChange={(e) => onPatch({ store: e.target.value })}><option value="">Not set</option>{stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
        <label className="toggle-row">Aisle <select className="field" value={item.aisle} onChange={(e) => onPatch({ aisle: e.target.value })}>{aisles.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
        <label className="toggle-row">In my pantry <input type="checkbox" checked={item.from_pantry} onChange={(e) => onFlags({ have: e.target.checked })} /></label>
        <label className="toggle-row">Always check off <input type="checkbox" checked={item.never_shop} onChange={(e) => onFlags({ never_shop: e.target.checked })} /></label>
        </div>
      </div>
    </section>
  );
}

function StoresView({ stores, lines, newStore, setNewStore, err, onBack, onAssign, onAdd, onRemove, onAisles }) {
  return (
    <section className="screen">
      <header className="top sub">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Back">
          ←
        </button>
        <h1>Stores</h1>
      </header>
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        <p className="help" data-tip="grocery.stores">Add or remove stores and assign each grocery item.</p>
        <button type="button" className="list-link" onClick={onAisles}>
          Aisles
        </button>
        <h3 className="block-label">Your stores</h3>
        {stores.map((s) => (
          <div key={s.id} className="store-edit">
            <strong>{s.name}</strong>
            {stores.length > 1 && (
              <button type="button" className="text-link" onClick={() => onRemove(s.id)}>
                Remove
              </button>
            )}
          </div>
        ))}
        <form
          className="add-line"
          onSubmit={(e) => {
            e.preventDefault();
            onAdd();
          }}
        >
          <input className="field" placeholder="Add a store" value={newStore} onChange={(e) => setNewStore(e.target.value)} />
          <button type="submit" className="btn-secondary">
            Add
          </button>
        </form>
        <h3 className="block-label">Assign items</h3>
        {lines.map((l) => (
          <div key={l.id} className="store-assign">
            <strong>{l.name}</strong>
            <div className="chip-row wrap">
              {stores.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`chip${(l.store || stores[0]?.id) === s.id ? " is-on" : ""}`}
                  onClick={() => onAssign(l.id, s.id)}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function AislesView({ aisles, lines = [], err, onBack, onChange, onAssign }) {
  function move(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= aisles.length) return;
    const next = aisles.slice();
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  }
  return (
    <section className="screen">
      <header className="top sub">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Back">
          ←
        </button>
        <h1>Aisles</h1>
      </header>
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        <p className="help" data-tip="grocery.aisles">Set aisle numbers and order, then put each grocery item in an aisle.</p>
        {aisles.map((a, i) => (
          <div key={a.id} className="aisle-edit">
            <strong>{a.name}</strong>
            <input
              className="field tight aisle-num"
              placeholder="#"
              value={a.number}
              onChange={(e) => onChange(aisles.map((x) => (x.id === a.id ? { ...x, number: e.target.value } : x)))}
            />
            <button type="button" className="icon-btn" onClick={() => move(i, -1)} aria-label="Move up">
              ↑
            </button>
            <button type="button" className="icon-btn" onClick={() => move(i, 1)} aria-label="Move down">
              ↓
            </button>
          </div>
        ))}
        {onAssign ? (
          <>
            <h3 className="block-label">Assign items</h3>
            {lines.map((l) => (
              <div key={l.id} className="store-assign">
                <strong>{l.name}</strong>
                <div className="chip-row wrap">
                  {aisles.map((a) => (
                    <button
                      key={a.id}
                      type="button"
                      className={`chip${(l.aisle || "other") === a.id ? " is-on" : ""}`}
                      onClick={() => onAssign(l.id, a.id)}
                    >
                      {a.name}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </>
        ) : null}
      </div>
    </section>
  );
}
