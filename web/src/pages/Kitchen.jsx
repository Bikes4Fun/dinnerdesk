import { useEffect, useMemo, useState } from "react";
import { GroceryPick } from "../GroceryPick.jsx";
import { onListKeys } from "../listKeys.js";
import { api } from "../api.js";
import { go } from "../nav.js";
import { Tip } from "../Tip.jsx";

function Back({ to = "/kitchen" }) {
  return (
    <button type="button" className="icon-btn" onClick={() => go(to)} aria-label="Back">
      ←
    </button>
  );
}

function CheckRow({ name, checked, onToggle }) {
  return (
    <button type="button" className="p-check" role="checkbox" aria-checked={checked} onClick={onToggle}>
      <span className={`box${checked ? " is-on" : ""}`}>{checked ? "✓" : ""}</span>
      <span className="g-name">{name}</span>
    </button>
  );
}

export function Kitchen({ view = "hub" }) {
  if (view === "pantry") return <PantryHave />;
  if (view === "pantry-add") return <PantryAdd />;
  if (view === "always-checked") return <AlwaysChecked />;
  if (view === "overrides") return <Overrides />;
  if (view === "stores") return <Stores />;
  if (view === "aisles") return <Aisles />;
  if (view === "templates") return <Templates />;
  return <KitchenHub />;
}

function KitchenHub() {
  const [portions, setPortions] = useState(4);
  const [alwaysN, setAlwaysN] = useState(null);
  const [overrideN, setOverrideN] = useState(null);
  const [syncSoon, setSyncSoon] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .household()
      .then((hh) => {
        const n = Number(hh.prefs?.family_portions);
        if (n >= 1) setPortions(n);
      })
      .catch((e) => setErr(e.message));
    api
      .pantry()
      .then((d) => setAlwaysN((d.items || []).filter((i) => i.never_shop).length))
      .catch((e) => setErr(e.message));
    api
      .overrides()
      .then((d) => setOverrideN((d.items || []).length))
      .catch((e) => setErr(e.message));
  }, []);

  async function savePortions(value) {
    const n = Math.max(1, Math.min(50, Number(value) || 1));
    setPortions(n);
    try {
      // Only this key: the server merges top-level prefs (#172).
      await api.putHousehold({ prefs: { family_portions: n } });
    } catch (e) {
      setErr(e.message);
    }
  }

  // Layout mirrors iOS Kitchen: Everyday / Shopping / General / Coming soon.
  return (
    <section className="screen">
      <header className="top">
        <button type="button" className="icon-btn mob-back" onClick={() => go("/more")} aria-label="Back">
          ←
        </button>
        <h1>My kitchen</h1>
      </header>
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        <label className="block-label">Everyday</label>
        <button type="button" className="list-link" onClick={() => go("/settings/filters")}>
          Filters
        </button>
        <button type="button" className="list-link" onClick={() => go("/recipes?list=mine")}>
          My recipes
        </button>
        <button type="button" className="list-link" onClick={() => go("/kitchen/pantry")}>
          Pantry
        </button>
        <label className="block-label">Shopping</label>
        <button type="button" className="list-link" onClick={() => go("/kitchen/stores")}>
          Stores &amp; aisles
        </button>
        <button type="button" className="list-link" onClick={() => go("/kitchen/always-checked")}>
          Always checked off {alwaysN != null ? <em>{alwaysN}</em> : null}
        </button>
        <label className="portions-row">
          Portions
          <input
            className="portions-input"
            type="number"
            min="1"
            value={portions}
            onChange={(e) => savePortions(e.target.value)}
          />
        </label>
        <label className="block-label">General</label>
        <button type="button" className="list-link" onClick={() => go("/recipes?list=hidden")}>
          Hidden recipes
        </button>
        <button type="button" className="list-link" onClick={() => go("/kitchen/overrides")}>
          Substitutions {overrideN != null ? <em>{overrideN}</em> : null}
        </button>
        <label className="block-label">Coming soon</label>
        <button type="button" className="list-link" onClick={() => go("/kitchen/templates")}>
          Recipe templates
          <em>Coming soon</em>
        </button>
        <button type="button" className="list-link" disabled>
          New to cooking
          <em>Coming soon</em>
        </button>
        <button type="button" className="list-link" onClick={() => setSyncSoon((on) => !on)}>
          Sync nutrition data
          <em>Coming soon</em>
        </button>
        {syncSoon ? (
          <p className="help">
            Coming soon: when you cook a meal, we’ll send that serving’s calories and macros to
            Apple Health so Lose It, Cronometer, and other trackers can log it.
          </p>
        ) : null}
      </div>
    </section>
  );
}

function PantryHave() {
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [autoCheck, setAutoCheck] = useState(false);
  const [err, setErr] = useState("");
  // Select mode: tick several items and apply one change to all of them (#187).
  const [picking, setPicking] = useState(false);
  const [picked, setPicked] = useState(new Set());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .pantry()
      .then((d) => setItems((d.items || []).filter((i) => i.have)))
      .catch((e) => setErr(e.message));
    api
      .household()
      .then((hh) => setAutoCheck(Boolean(hh.prefs?.pantry_auto_check)))
      .catch((e) => setErr(e.message));
  }, []);

  // Same switch as the iPhone's Pantry: the server checks or unchecks pantry items on this
  // week's grocery list when it changes, so send only this one pref.
  async function saveAutoCheck(on) {
    setAutoCheck(on);
    setErr("");
    try {
      await api.putHousehold({ prefs: { pantry_auto_check: on } });
    } catch (e) {
      setAutoCheck(!on);
      setErr(e.message);
    }
  }

  function togglePick(id) {
    setPicked((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function leavePicking() {
    setPicking(false);
    setPicked(new Set());
  }

  // One change applied to every ticked item. `patch` is whatever patchPantry takes.
  async function applyToPicked(patch, drop) {
    const chosen = items.filter((i) => picked.has(i.id));
    if (!chosen.length) return;
    setBusy(true);
    setErr("");
    try {
      const updated = await Promise.all(chosen.map((i) => api.patchPantry(i.id, patch)));
      const byId = new Map(updated.map((i) => [i.id, i]));
      setItems((cur) => (drop ? cur.filter((i) => !byId.has(i.id)) : cur.map((i) => byId.get(i.id) || i)));
      leavePicking();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (selected) return <PantryItem item={selected} onBack={() => { setSelected(null); api.pantry().then((d) => setItems(d.items.filter((i) => i.have))); }} />;

  const allPicked = picked.size > 0 && picked.size === items.length;
  const pickedItems = items.filter((i) => picked.has(i.id));
  // One button that undoes itself, like Plan's Mark cooked / Mark uncooked.
  const allNeverShop = pickedItems.length > 0 && pickedItems.every((i) => i.never_shop);

  return (
    <section className="screen">
      <header className="top sub">
        <Back />
        <h1>Pantry</h1>
        {picking ? (
          <button type="button" className="text-link" onClick={leavePicking}>Done</button>
        ) : items.length > 0 ? (
          <button type="button" className="text-link" onClick={() => setPicking(true)}>Select</button>
        ) : (
          <button type="button" className="text-link" onClick={() => go("/kitchen/pantry/add")}>Add items</button>
        )}
      </header>
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        <Tip id="kitchen.pantry">What you already have.</Tip>
        <label className="toggle-row">Always check off pantry items <input type="checkbox" checked={autoCheck} onChange={(e) => saveAutoCheck(e.target.checked)} /></label>
        {picking && items.length > 0 && (
          <div className="plan-bulk">
            <button type="button" onClick={() => setPicked(allPicked ? new Set() : new Set(items.map((i) => i.id)))}>
              {allPicked ? "Deselect all" : "Select all"}
            </button>
            <span>{picked.size} selected</span>
          </div>
        )}
        {items.length === 0 && <p className="empty-block">Nothing checked yet. Add items from the catalog.</p>}
        {items.map((item) => (
          // The whole row is the target, not just the name (#187).
          <button
            key={item.id}
            type="button"
            className={`have-row${picking && picked.has(item.id) ? " is-picked" : ""}`}
            aria-pressed={picking ? picked.has(item.id) : undefined}
            onClick={() => (picking ? togglePick(item.id) : setSelected(item))}
          >
            {picking && <span className="have-tick" aria-hidden="true">{picked.has(item.id) ? "✓" : ""}</span>}
            <span className="have-name">{item.name}</span>
            {item.never_shop ? <em>never shop</em> : null}
            {!picking && <span className="have-chev" aria-hidden="true">›</span>}
          </button>
        ))}
        {!picking && (
          <>
            <button type="button" className="ghost-add" onClick={() => go("/kitchen/pantry/add")}>
              + Add or edit items
            </button>
            <button type="button" className="list-foot-link" onClick={() => go("/kitchen/stores")}>
              Grocery store
            </button>
          </>
        )}
      </div>
      {picking && (
        <div className="pantry-bulk-bar">
          <button
            type="button"
            className="btn-primary"
            disabled={busy || picked.size === 0}
            onClick={() => applyToPicked({ never_shop: !allNeverShop })}
          >
            {allNeverShop ? "Stop always checking off" : "Always check off"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={busy || picked.size === 0}
            onClick={() => applyToPicked({ have: false }, true)}
          >
            Remove from pantry
          </button>
        </div>
      )}
    </section>
  );
}

function PantryAdd() {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const [ranked, setRanked] = useState(null);
  const [custom, setCustom] = useState("");
  const [adding, setAdding] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.pantryCatalog().then((d) => setItems(d.items || [])).catch((e) => setErr(e.message));
  }, []);

  useEffect(() => {
    const needle = q.trim();
    if (!needle) {
      setRanked(null);
      return;
    }
    const t = setTimeout(() => {
      api
        .groceryItems(needle, 40)
        .then((d) => setRanked(d))
        .catch((e) => setErr(e.message));
    }, 80);
    return () => clearTimeout(t);
  }, [q]);

  const visible = useMemo(() => {
    if (!ranked) return items;
    const map = new Map(items.map((i) => [i.name.toLowerCase(), i]));
    const rows = (ranked.items || []).map(
      (h) => map.get(h.name.toLowerCase()) || { name: h.name, have: false, never_shop: false, quantity: "", zone: "dry" },
    );
    const extra = (ranked.custom || "").trim();
    if (extra && !rows.some((r) => r.name.toLowerCase() === extra.toLowerCase())) {
      rows.push({ name: extra, have: false, never_shop: false, quantity: "", zone: "dry" });
    }
    return rows;
  }, [items, ranked]);

  async function toggle(item) {
    try {
      const next = await api.upsertPantry({
        name: item.name,
        have: !item.have,
        never_shop: item.never_shop,
        quantity: item.quantity || "",
        zone: item.zone || "dry",
      });
      setItems((cur) => {
        const rest = cur.filter((x) => x.name.toLowerCase() !== next.name.toLowerCase());
        return [...rest, { ...item, ...next, catalog: item.catalog }].sort((a, b) =>
          a.name.localeCompare(b.name),
        );
      });
    } catch (e) {
      setErr(e.message);
    }
  }

  async function addCustom(e) {
    e.preventDefault();
    const name = custom.trim();
    if (!name) return;
    try {
      const next = await api.upsertPantry({ name, have: true, never_shop: false, zone: "dry" });
      setItems((cur) => {
        const rest = cur.filter((x) => x.name.toLowerCase() !== next.name.toLowerCase());
        return [...rest, { ...next, catalog: false }].sort((a, b) => a.name.localeCompare(b.name));
      });
      setCustom("");
      setAdding(false);
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <section className="screen">
      <header className="top sub">
        <Back to="/kitchen/pantry" />
        <h1>Add items</h1>
        <button type="button" className="text-link" onClick={() => go("/kitchen/pantry")}>
          Done
        </button>
      </header>
      <div className="scroll pad" onKeyDown={(e) => { if (e.target.closest(".add-line")) return; onListKeys(e, ".p-check", ".field-input"); }}>
        {err && <p className="banner err">{err}</p>}
        <Tip id="kitchen.pantry-add">Check what you have. Saves as you go — tap Done when you’re finished.</Tip>
        <button type="button" className="ghost-add" onClick={() => setAdding((v) => !v)}>
          {adding ? "Cancel custom item" : "+ Add a custom item"}
        </button>
        {adding && (
          <form className="add-line" onSubmit={addCustom}>
            <input
              className="field"
              aria-label="Custom ingredient"
              placeholder="Custom ingredient"
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
              autoFocus
            />
            <button type="submit" className="btn-secondary">
              Add
            </button>
          </form>
        )}
        <input
          className="field-input"
          placeholder="Search items…"
          aria-label="Search items"
          autoComplete="off"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        {ranked && q.trim() && ranked.note === "ideas" ? (
          <p className="search-note">No exact match. Closest items:</p>
        ) : null}
        {ranked && q.trim() && ranked.note === "closest" ? (
          <p className="search-note">No item used every word. Closest matches:</p>
        ) : null}
        {visible.map((item) => (
          <CheckRow
            key={item.id || item.name}
            name={item.name}
            checked={item.have}
            onToggle={() => toggle(item)}
          />
        ))}
      </div>
    </section>
  );
}

function AlwaysChecked() {
  const [items, setItems] = useState([]);
  const [name, setName] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .pantry()
      .then((d) => setItems((d.items || []).filter((i) => i.never_shop)))
      .catch((e) => setErr(e.message));
  }, []);

  async function addItem(raw) {
    const n = (raw || "").trim();
    if (!n) return;
    try {
      const next = await api.upsertPantry({ name: n, have: true, never_shop: true, zone: "dry" });
      setItems((cur) => {
        const rest = cur.filter((x) => x.id !== next.id && x.name.toLowerCase() !== next.name);
        return [...rest, next].sort((a, b) => a.name.localeCompare(b.name));
      });
      setName("");
    } catch (e) {
      setErr(e.message);
    }
  }

  async function add(e) {
    e.preventDefault();
    await addItem(name);
  }

  async function remove(item) {
    try {
      const next = await api.patchPantry(item.id, { never_shop: false });
      setItems((cur) => cur.filter((x) => x.id !== next.id));
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <section className="screen">
      <header className="top sub">
        <Back />
        <h1>Always checked off</h1>
        <span />
      </header>
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        <Tip id="kitchen.always-checked">
          Things you always have on hand, like salt or oil. They still appear on your grocery list,
          but already checked off, so you can skip them unless you run low.
        </Tip>
        {items.length === 0 && <div className="pantry-examples" aria-label="Examples only">
          <p>Examples — add what you always keep on hand</p><p>Salt</p><p>Olive oil</p><p>Black pepper</p>
        </div>}
        {items.map((item) => (
          <div key={item.id} className="have-row">
            <strong>{item.name}</strong>
            <button type="button" className="text-link" onClick={() => remove(item)}>
              Remove
            </button>
          </div>
        ))}
        <label className="block-label">Add an item</label>
        <form onSubmit={add}>
          <GroceryPick
            value={name}
            onChange={setName}
            onPick={addItem}
            placeholder="Search items…"
          />
          <button type="submit" className="btn-primary block">
            Always check off
          </button>
        </form>
      </div>
    </section>
  );
}

function Overrides() {
  const [items, setItems] = useState([]);
  const [fromName, setFromName] = useState("");
  const [toName, setToName] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    api.overrides().then((d) => setItems(d.items || [])).catch((e) => setErr(e.message));
  }, []);

  async function add(e) {
    e.preventDefault();
    if (!fromName.trim() || !toName.trim()) return;
    try {
      const data = await api.addOverride({ from_name: fromName.trim(), to_name: toName.trim() });
      setItems(data.items || []);
      setFromName("");
      setToName("");
    } catch (e) {
      setErr(e.message);
    }
  }

  async function remove(id) {
    try {
      const data = await api.deleteOverride(id);
      setItems(data.items || []);
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <section className="screen">
      <header className="top sub">
        <Back />
        <h1>Ingredient overrides</h1>
        <span />
      </header>
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        {items.map((it) => (
          <div key={it.id} className="have-row substitution-row">
            <strong>
              {it.from_name} → {it.to_name}
            </strong>
            <button type="button" className="text-link" onClick={() => remove(it.id)}>
              Remove
            </button>
          </div>
        ))}
        <form onSubmit={add}>
          <label className="block-label">When a recipe calls for</label>
          <GroceryPick
            value={fromName}
            onChange={setFromName}
            placeholder="chicken thighs, bone-in skin-on"
          />
          <label className="block-label">Replacement item</label>
          <GroceryPick
            value={toName}
            onChange={setToName}
            placeholder="chicken thighs, boneless skinless"
          />
          <button type="submit" className="btn-primary block">
            Save substitution
          </button>
        </form>
      </div>
    </section>
  );
}

const KITCHEN_AISLES = [
  { id: "produce", name: "Produce", number: "" },
  { id: "dairy", name: "Dairy, Cheese & Eggs", number: "" },
  { id: "meat", name: "Meat & Seafood", number: "" },
  { id: "pantry", name: "Pantry", number: "" },
  { id: "deli", name: "Deli", number: "" },
  { id: "frozen", name: "Frozen", number: "" },
  { id: "other", name: "Other", number: "" },
];

function Stores() {
  const [stores, setStores] = useState([]);
  const [lines, setLines] = useState([]);
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  // Removing a store unassigns its items, so confirm first and say how many (#187).
  const [doomed, setDoomed] = useState(null);
  // Renaming keeps the store's id, so every item stays assigned to it.
  const [renaming, setRenaming] = useState(null);
  const [renamedTo, setRenamedTo] = useState("");

  useEffect(() => {
    Promise.all([api.household(), api.plan()])
      .then(async ([hh, plan]) => {
        const g = hh.prefs?.grocery || {};
        setStores(Array.isArray(g.stores) && g.stores.length ? g.stores : []);
        const data = await api.grocery(plan.id);
        setLines(data.lines || []);
      })
      .catch((e) => setErr(e.message));
  }, []);

  async function persist(next) {
    setStores(next);
    try {
      const hh = await api.household();
      const grocery = { ...(hh.prefs?.grocery || {}), stores: next };
      await api.putHousehold({ prefs: { grocery } });
    } catch (e) {
      setErr(e.message);
    }
  }

  async function assign(id, store) {
    setLines((cur) => cur.map((l) => (l.id === id ? { ...l, store } : l)));
    try {
      await api.patchGrocery(id, { store });
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <section className="screen">
      <header className="top sub">
        <Back />
        <h1>Grocery store</h1>
        <span />
      </header>
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        <Tip id="kitchen.stores">Add or remove stores and assign each grocery item.</Tip>
        <button type="button" className="list-link" onClick={() => go("/kitchen/aisles")}>
          Aisles
        </button>
        <h3 className="block-label">Your stores</h3>
        {stores.map((s) => {
          const used = lines.filter((l) => l.store === s.id).length;
          if (renaming === s.id) {
            return (
              <form
                key={s.id}
                className="add-line"
                onSubmit={(e) => {
                  e.preventDefault();
                  const n = renamedTo.trim();
                  // Keep the id so assignments survive; only the name people see changes.
                  if (n && n !== s.name) persist(stores.map((x) => (x.id === s.id ? { ...x, name: n } : x)));
                  setRenaming(null);
                }}
              >
                <input className="field" aria-label={`Rename ${s.name}`} value={renamedTo} onChange={(e) => setRenamedTo(e.target.value)} autoFocus />
                <button type="submit" className="btn-secondary">Save</button>
                <button type="button" className="text-link" onClick={() => setRenaming(null)}>Cancel</button>
              </form>
            );
          }
          return (
            <div key={s.id} className="store-edit">
              <strong>{s.name}</strong>
              <span className="store-count">{used === 1 ? "1 item" : `${used} items`}</span>
              <button type="button" className="text-link" onClick={() => { setRenamedTo(s.name); setRenaming(s.id); }}>
                Rename
              </button>
              <button type="button" className="text-link" onClick={() => setDoomed(s)}>
                Remove
              </button>
            </div>
          );
        })}
        {doomed && (
          <div className="store-confirm" role="alertdialog" aria-label={`Remove ${doomed.name}?`}>
            <p>
              <strong>Remove {doomed.name}?</strong>{" "}
              {(() => {
                const n = lines.filter((l) => l.store === doomed.id).length;
                if (!n) return "No items are assigned to it. You can add it back anytime.";
                return `${n === 1 ? "1 item moves" : `${n} items move`} to Any store. You can add it back anytime.`;
              })()}
            </p>
            <div className="store-confirm-actions">
              <button type="button" className="btn-secondary" onClick={() => setDoomed(null)}>Cancel</button>
              <button
                type="button"
                className="btn-danger"
                onClick={() => { persist(stores.filter((x) => x.id !== doomed.id)); setDoomed(null); }}
              >
                Remove
              </button>
            </div>
          </div>
        )}
        <form
          className="add-line"
          onSubmit={(e) => {
            e.preventDefault();
            const n = name.trim();
            if (!n) return;
            const id = n.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "store";
            persist([...stores, { id, name: n }]);
            setName("");
          }}
        >
          <input className="field" aria-label="New store name" placeholder="Add a store" value={name} onChange={(e) => setName(e.target.value)} />
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
                  className={`chip${l.store === s.id ? " is-on" : ""}`}
                  onClick={() => assign(l.id, s.id)}
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

function Aisles() {
  const [aisles, setAisles] = useState(KITCHEN_AISLES);
  const [lines, setLines] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    Promise.all([api.household(), api.plan()])
      .then(async ([hh, plan]) => {
        const g = hh.prefs?.grocery || {};
        setAisles(Array.isArray(g.aisles) && g.aisles.length ? g.aisles : KITCHEN_AISLES);
        const data = await api.grocery(plan.id);
        setLines(data.lines || []);
      })
      .catch((e) => setErr(e.message));
  }, []);

  async function persist(next) {
    setAisles(next);
    try {
      const hh = await api.household();
      const grocery = { ...(hh.prefs?.grocery || {}), aisles: next };
      await api.putHousehold({ prefs: { grocery } });
    } catch (e) {
      setErr(e.message);
    }
  }

  function move(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= aisles.length) return;
    const next = aisles.slice();
    [next[i], next[j]] = [next[j], next[i]];
    persist(next);
  }

  async function assign(id, aisle) {
    setLines((cur) => cur.map((l) => (l.id === id ? { ...l, aisle } : l)));
    try {
      await api.patchGrocery(id, { aisle });
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <section className="screen">
      <header className="top sub">
        <Back to="/kitchen/stores" />
        <h1>Aisles</h1>
      </header>
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        <Tip id="kitchen.aisles">Set aisle numbers and order, then put each grocery item in an aisle.</Tip>
        {aisles.map((a, i) => (
          <div key={a.id} className="aisle-edit">
            <strong>{a.name}</strong>
            <input
              className="field tight aisle-num"
              aria-label={`Aisle number for ${a.name}`}
              placeholder="#"
              value={a.number}
              onChange={(e) => persist(aisles.map((x) => (x.id === a.id ? { ...x, number: e.target.value } : x)))}
            />
            <button type="button" className="icon-btn" onClick={() => move(i, -1)} aria-label={`Move ${a.name} up`}>
              ↑
            </button>
            <button type="button" className="icon-btn" onClick={() => move(i, 1)} aria-label={`Move ${a.name} down`}>
              ↓
            </button>
          </div>
        ))}
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
                  onClick={() => assign(l.id, a.id)}
                >
                  {a.name}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function prettyFamily(id) {
  return String(id || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function Templates() {
  const [families, setFamilies] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.templates().then((d) => setFamilies(d.families || [])).catch((e) => setErr(e.message));
  }, []);

  return (
    <section className="screen">
      <header className="top sub">
        <Back />
        <h1>Templates</h1>
        <span />
      </header>
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        <Tip id="kitchen.templates">Pick a format. Recipe bodies live in the cookbook.</Tip>
        {families.map((f) => (
          <button
            key={f.id}
            type="button"
            className="list-link"
            onClick={() => go(`/recipes?family=${encodeURIComponent(f.id)}`)}
          >
            {prettyFamily(f.name || f.id)}
            <em>{(f.recipes || []).length}</em>
          </button>
        ))}
      </div>
    </section>
  );
}

function PantryItem({ item, onBack }) {
  const [amount, setAmount] = useState(item.quantity);
  const [have, setHave] = useState(item.have);
  const [neverShop, setNeverShop] = useState(item.never_shop);
  const [stores, setStores] = useState([]);
  const [aisles, setAisles] = useState([]);
  const [place, setPlace] = useState(null);
  useEffect(() => {
    Promise.all([api.household(), api.placements()]).then(([hh, data]) => {
      setStores(hh.prefs.grocery?.stores || []);
      setAisles(hh.prefs.grocery?.aisles || KITCHEN_AISLES);
      setPlace(data.items.find((p) => p.name.toLowerCase() === item.name.toLowerCase()));
    });
  }, [item.id]);
  async function placement(body) {
    await api.setPlacement({ name: item.name, ...body });
    setPlace((p) => ({ ...p, ...body }));
  }
  return <section className="screen">
    <header className="top sub"><button className="icon-btn" onClick={onBack}>←</button><h1>{item.name}</h1></header>
    <div className="scroll pad">
      <label className="toggle-row">Have this item <input type="checkbox" checked={have} onChange={async (e) => { const value = e.target.checked; await api.patchPantry(item.id, { have: value }); setHave(value); }} /></label>
      <label className="toggle-row">Always check off <input type="checkbox" checked={neverShop} onChange={async (e) => { const value = e.target.checked; await api.patchPantry(item.id, { never_shop: value }); setNeverShop(value); }} /></label>
      <label className="block-label" htmlFor="pantry-amount">Amount</label><input id="pantry-amount" className="field" value={amount} onChange={(e) => setAmount(e.target.value)} onBlur={() => api.patchPantry(item.id, { quantity: amount })} />
      {place && <>
        <label className="block-label" htmlFor="pantry-store">Store</label><select id="pantry-store" className="field" value={place.store} onChange={(e) => placement({ store: e.target.value })}><option value="">Not set</option>{stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <label className="block-label" htmlFor="pantry-aisle">Aisle</label><select id="pantry-aisle" className="field" value={place.aisle} onChange={(e) => placement({ aisle: e.target.value })}>{aisles.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select>
      </>}
      <button className="text-link danger" onClick={async () => { await api.deletePantry(item.id); onBack(); }}>Delete item</button>
    </div>
  </section>;
}
