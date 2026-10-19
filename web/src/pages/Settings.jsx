import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { ADMIN_PAGES, go } from "../nav.js";
import { ALLERGENS, AVOIDS, CUISINES, DIETS, PROTEINS, WHO, cleanDiets, otherWords, toggleAvoid, toggleDiet } from "../diet.js";
import { Tip } from "../Tip.jsx";

function Back() {
  return (
    <button type="button" className="icon-btn mob-back" onClick={() => go("/more")} aria-label="Back">
      ←
    </button>
  );
}

function Link({ href, children, extra, onClick }) {
  return (
    <button type="button" className="list-link" onClick={onClick || (() => go(href))}>
      {children}
      {extra ? <em>{extra}</em> : null}
    </button>
  );
}

export function Settings() {
  const [authEmail, setAuthEmail] = useState("");
  const [admin, setAdmin] = useState(false);
  const [syncSoon, setSyncSoon] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.auth
      .status()
      .then((s) => {
        setAuthEmail(s.email || "");
        setAdmin(Boolean(s.admin));
      })
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <section className="screen">
      <header className="top">
        <Back />
        <h1>Settings</h1>
      </header>
      <div className="scroll pad">
        {err && <p className="banner err" role="alert">{err}</p>}
        <Link href="/settings/filters">Filters</Link>
        <Link href="/settings/account" extra={authEmail || "Not signed in"}>
          Account &amp; security
        </Link>
        <Link
          onClick={() => {
            window.dispatchEvent(new Event("dinnerdesk-tour"));
          }}
        >
          Quick start tour
        </Link>
        <Link href="/settings/social">Social</Link>
        <Link href="/settings/newsletter">Email newsletter</Link>
        <Link href="/support">Help &amp; support</Link>
        <Link href="/settings/feedback">Report a bug or suggest a feature</Link>
        <Link href="/privacy">Privacy</Link>
        <a className="list-link" href="https://x.com/DinnerDesk" target="_blank" rel="noopener noreferrer">
          Twitter
          <em>@DinnerDesk</em>
        </a>
        {admin ? (
          <>
            <Link href="/settings/ingredients" extra="Answers only">
              Ingredient review
            </Link>
            <Link href="/settings/recipe-flags" extra="Manual edits">
              Recipes to edit
            </Link>
            <Link href="/settings/feedback-inbox" extra="Admin">
              Bugs &amp; ideas inbox
            </Link>
            {ADMIN_PAGES.map(([href, label]) => (
              <a key={href} className="list-link" href={href}>
                {label}
                <em>Admin</em>
              </a>
            ))}
          </>
        ) : null}
        <Link href="/settings/tastelab">Taste Lab</Link>
        <Link extra="Coming soon" onClick={() => setSyncSoon(true)}>
          Nutrition tracker sync
        </Link>
        {syncSoon ? (
          <p className="help">
            Coming soon: when you cook a meal, we’ll send that serving’s calories and macros to
            Apple Health so Lose It, Cronometer, and other trackers can log it.
          </p>
        ) : null}
        <label className="block-label">About recipes &amp; photos</label>
        <Tip id="settings.gold-star">
          A gold ★ means we (Dinnerdesk) have reviewed and tested the recipe. Only we
          can add that mark. It’s there so you can see which recipes we definitively trust. Other
          recipes still come from trusted sources; their photos are public-use or AI-generated. Real photos are updated as we test recipes.
        </Tip>
      </div>
    </section>
  );
}

const TIMES = [
  ["any", "Any time"],
  ["20", "20 min or less"],
  ["30", "30 min or less"],
  ["45", "45 min or less"],
];
// Same labels as Taste Lab's Filters screen.
const DIET_LABELS = { omnivore: "Omnivore", pescatarian: "Pescatarian", vegetarian: "Vegetarian", vegan: "Vegan", "gluten-free": "Gluten-free", "dairy-free": "Dairy-free" };

/** Chips for a list plus an Other box for words not on it. Saves the whole list. */
function FoodFilterPicker({ label, selected, onAdd, onRemove, query, onQuery, skip = [], quietEmpty = false, placeholder, dashed = false, presets = [] }) {
  const [ownQuery, setOwnQuery] = useState("");
  const q = query ?? ownQuery;
  const setQ = onQuery ?? setOwnQuery;
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setMatches([]);
    setError("");
    setLoading(Boolean(q.trim()));
    if (!q.trim()) return;
    const timer = setTimeout(() => api.filterItems(q)
      .then((box) => { if (active) setMatches(box.items.map((item) => item.name)); })
      .catch(() => { if (active) setError("Couldn't search foods. Please try again."); })
      .finally(() => { if (active) setLoading(false); }), 250);
    return () => { active = false; clearTimeout(timer); };
  }, [q]);
  const controlled = query != null;
  const presetHits = presets.filter((name) => q.trim() && name.toLowerCase().includes(q.trim().toLowerCase()) && !selected.includes(name));
  return <div className="filter-food-picker">
    {!controlled && !dashed && <div className="chip-row wrap">{selected.map((name) => <button type="button" className="chip is-on" key={name} aria-label={`Remove ${name}`} onClick={() => onRemove(name)}>{name} ×</button>)}</div>}
    {!controlled && <label><input className={dashed ? "filter-search" : "field"} aria-label={`Search ${label.toLowerCase()}`} placeholder={placeholder || "Search foods, e.g. bell peppers or ground"} value={q} onChange={(event) => setQ(event.target.value)} /></label>}
    {loading && <p role="status">Searching…</p>}
    {error && <p role="alert">{error}</p>}
    {presetHits.length > 0 && <div className="chip-row wrap filter-chips">{presetHits.map((name) => <button type="button" className="filter-choice" key={name} onClick={() => { onAdd(name); setQ(""); }}>+ {name}</button>)}</div>}
    {/* Matches as chips (#85): tap one to add it. */}
    <div className="chip-row wrap filter-food-results">{matches.filter((name) => !selected.includes(name) && !skip.includes(name.toLowerCase())).map((name) => <button type="button" className="chip" key={name} aria-label={`Add ${name}`} onClick={() => { onAdd(name); setQ(""); }}>+ {name}</button>)}</div>
    {!quietEmpty && !loading && !error && q.trim() && !matches.length && <p role="status">No matching foods. Try another name.</p>}
  </div>;
}

function ChoiceBlock({ label, items, saved, onChange, otherLabel, compact }) {
  const custom = otherWords(saved, items);
  const [open, setOpen] = useState(custom.length > 0);
  const [query, setQuery] = useState("");
  useEffect(() => { if (custom.length) setOpen(true); }, [custom.join("\u001f")]);
  if (compact) {
    const q = query.trim().toLowerCase();
    const presets = items
      .map((item) => (Array.isArray(item) ? item : [item, item]))
      .filter(([id, text]) => q && text.toLowerCase().includes(q) && !saved.includes(id));
    return (
      <>
        {label && <h3 className="block-label">{label}</h3>}
        <div className="chip-row wrap filter-chips">
          {saved.map((id) => {
            const named = items.find((item) => (Array.isArray(item) ? item[0] : item) === id);
            const text = Array.isArray(named) ? named[1] : id;
            return (
              <button key={id} type="button" className="chip is-on" aria-label={`Remove ${text}`} onClick={() => onChange(saved.filter((word) => word !== id))}>
                {text} ×
              </button>
            );
          })}
        </div>
        <label>
          <input className="field" aria-label={`Search ${label.toLowerCase()}`} placeholder="Search foods to avoid" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        {presets.length > 0 && (
          <div className="chip-row wrap filter-chips">
            {presets.map(([id, text]) => (
              <button key={id} type="button" className="chip" aria-label={`Add ${text}`} onClick={() => { onChange([...saved, id]); setQuery(""); }}>+ {text}</button>
            ))}
          </div>
        )}
        {q && <FoodFilterPicker label={otherLabel} selected={custom} query={query} onQuery={setQuery} skip={items.map((item) => (Array.isArray(item) ? item[0] : item))} quietEmpty={presets.length > 0} onAdd={(name) => onChange([...new Set([...saved, name])])} onRemove={(name) => onChange(saved.filter((word) => word !== name))} />}
      </>
    );
  }
  return (
    <>
      {label && <h3 className="block-label">{label}</h3>}
      <div className="chip-row wrap filter-chips">
        <button type="button" className={`chip${saved.length ? "" : " is-on"}`} aria-pressed={!saved.length} onClick={() => { setOpen(false); onChange([]); }}>
          None
        </button>
        {items.map((item) => {
          const [id, text] = Array.isArray(item) ? item : [item, item];
          const on = saved.includes(id);
          return (
            <button key={id} type="button" className={`chip${on ? " is-on" : ""}`} aria-pressed={on} onClick={() => onChange(toggleAvoid(saved, id))}>
              {text}
            </button>
          );
        })}
        <button type="button" className={`chip${open ? " is-on" : ""}`} aria-expanded={open} onClick={() => setOpen(!open)}>
          Other
        </button>
      </div>
      {open && <FoodFilterPicker label={otherLabel} selected={custom} onAdd={(name) => onChange([...new Set([...saved, name])])} onRemove={(name) => onChange(saved.filter((word) => word !== name))} />}

    </>
  );
}

export function Filters() {
  const [diets, setDiets] = useState(["omnivore"]);
  const [allergens, setAllergens] = useState([]);
  const [avoids, setAvoids] = useState([]);
  const [time, setTime] = useState("any");
  const [who, setWho] = useState([]);
  const [cuisines, setCuisines] = useState([]);
  const [proteinMore, setProteinMore] = useState([]);
  const [proteinLess, setProteinLess] = useState([]);
  const [err, setErr] = useState("");
  const [saveState, setSaveState] = useState(""); // "", "saving", "saved" (#85)
  const [open, setOpen] = useState("");
  const saves = useRef(0);

  useEffect(() => {
    api
      .household()
      .then((hh) => {
        const f = hh.prefs?.filters || {};
        if (Array.isArray(f.diets)) setDiets(cleanDiets(f.diets));
        if (Array.isArray(f.allergens)) setAllergens(f.allergens);
        if (Array.isArray(f.avoids)) setAvoids(f.avoids);
        if (f.time) setTime(f.time);
        if (Array.isArray(f.who)) setWho(f.who);
        if (Array.isArray(f.cuisines)) setCuisines(f.cuisines);
        if (Array.isArray(f.protein_more)) setProteinMore(f.protein_more);
        if (Array.isArray(f.protein_less)) setProteinLess(f.protein_less);
      })
      .catch((e) => setErr(e.message));
  }, []);

  // The server merges filters, so send only what changed.
  async function setFilter(patch) {
    if ("diets" in patch) setDiets(patch.diets);
    if ("allergens" in patch) setAllergens(patch.allergens);
    if ("avoids" in patch) setAvoids(patch.avoids);
    if ("time" in patch) setTime(patch.time);
    if ("who" in patch) setWho(patch.who);
    if ("cuisines" in patch) setCuisines(patch.cuisines);
    if ("protein_more" in patch) setProteinMore(patch.protein_more);
    if ("protein_less" in patch) setProteinLess(patch.protein_less);
    const mine = ++saves.current;
    setSaveState("saving");
    try {
      await api.putHousehold({ prefs: { filters: patch } });
      setErr("");
      if (mine === saves.current) {
        setSaveState("saved");
        setTimeout(() => { if (mine === saves.current) setSaveState(""); }, 2000);
      }
    } catch (e) {
      if (mine === saves.current) setSaveState("");
      setErr(e.message);
    }
  }

  const showProteins = diets.includes("omnivore") || diets.includes("pescatarian");
  const proteinChoices = PROTEINS.filter(([id]) => diets.includes("omnivore") || id === "seafood");
  const filterCount = (diets.length === 1 && diets[0] === "omnivore" ? 0 : 1)
    + allergens.length + avoids.length + who.length + cuisines.length
    + proteinMore.length + proteinLess.length + (time === "any" ? 0 : 1);
  function reset() {
    setFilter({
      diets: ["omnivore"], allergens: [], avoids: [], time: "any",
      who: [], cuisines: [], protein_more: [], protein_less: [],
    });
  }
  function choice(label, on, pick) {
    return <button type="button" className={`filter-choice${on ? " is-on" : ""}`} aria-pressed={on} onClick={pick}>{label}</button>;
  }

  return (
    <section className="screen filters-screen">
      <header className="top sub">
        <button type="button" className="icon-btn" onClick={() => go("/settings")} aria-label="Back">
          ←
        </button>
        <h1>Filters</h1>
        <button type="button" className="text-link" onClick={reset}>Reset</button>
        <span className="save-state" role="status" aria-live="polite">{saveState === "saving" ? "Saving…" : saveState === "saved" ? "✓ Saved" : ""}</span>
      </header>
      <div className="scroll pad filters-body">
        {err && <p className="banner err">{err}</p>}
        <div className="filters-card">
          <div className="filters-kicker">
            <span className="filters-badge hide">Hides meals</span>
            <span>Strict — never shown</span>
          </div>
          <h2>Diet</h2>
          <div className="chip-row wrap filter-chips">
            {DIETS.map((d) => choice(DIET_LABELS[d] || d, diets.includes(d), () => setFilter({ diets: toggleDiet(diets, d) })))}
          </div>
          <h2>Allergies</h2>
          <div className="chip-row wrap filter-chips">
            {ALLERGENS.map(([id, text]) => choice(text, allergens.includes(id), () => setFilter({ allergens: allergens.includes(id) ? allergens.filter((a) => a !== id) : [...allergens, id] })))}
            {allergens.filter((id) => !ALLERGENS.some(([key]) => key === id)).map((id) => choice(`${id} ×`, true, () => setFilter({ allergens: allergens.filter((a) => a !== id) })))}
            {choice("Other", open === "allergies", () => setOpen(open === "allergies" ? "" : "allergies"))}
          </div>
          {open === "allergies" && <FoodFilterPicker label="Other allergies" selected={allergens.filter((id) => !ALLERGENS.some(([key]) => key === id))} onAdd={(name) => setFilter({ allergens: [...new Set([...allergens, name])] })} onRemove={(name) => setFilter({ allergens: allergens.filter((a) => a !== name) })} />}
          <h2>I avoid</h2>
          <div className="chip-row wrap filter-chips">
            {avoids.map((id) => choice(`${id} ×`, true, () => setFilter({ avoids: avoids.filter((a) => a !== id) })))}
          </div>
          <FoodFilterPicker label="Foods to avoid" selected={avoids} placeholder="Add an ingredient…" dashed presets={AVOIDS} onAdd={(name) => setFilter({ avoids: [...new Set([...avoids, name])] })} onRemove={(name) => setFilter({ avoids: avoids.filter((a) => a !== name) })} />
        </div>
        <div className="filters-soft">
          <div className="filters-kicker">
            <span className="filters-badge">Shapes suggestions</span>
            <span>Show me more of these</span>
          </div>
          <h2>Who it's for</h2>
          <div className="chip-row wrap filter-chips">
            {WHO.map(([id, text]) => choice(text, who.includes(id), () => setFilter({ who: who.includes(id) ? who.filter((w) => w !== id) : [...who, id] })))}
          </div>
          {showProteins && <>
            <h2>Proteins</h2>
            <div className="filter-tiles">
              {proteinChoices.map(([id, text]) => {
                const more = proteinMore.includes(id);
                const less = proteinLess.includes(id);
                const label = more ? `More ${text.toLowerCase()}` : less ? `Less ${text.toLowerCase()}` : text;
                return (
                  <button key={id} type="button" className={`filter-tile${more || less ? " is-on" : ""}`} aria-pressed={more || less} onClick={() => setFilter(more ? { protein_more: proteinMore.filter((p) => p !== id), protein_less: [...proteinLess, id] } : less ? { protein_less: proteinLess.filter((p) => p !== id) } : { protein_more: [...proteinMore, id], protein_less: proteinLess.filter((p) => p !== id) })}>
                    <span>{label}</span>
                    <span className="filter-check" aria-hidden="true">✓</span>
                  </button>
                );
              })}
            </div>
          </>}
          <h2>Cuisines</h2>
          <div className="chip-row wrap filter-chips">
            {CUISINES.map(([id, text]) => choice(text, cuisines.includes(id), () => setFilter({ cuisines: cuisines.includes(id) ? cuisines.filter((c) => c !== id) : [...cuisines, id] })))}
          </div>
          <h2>Cook time</h2>
          <div className="filter-time" role="radiogroup" aria-label="Cook time">
            {[["any", "Any"], ["20", "20 min"], ["30", "30 min"], ["45", "45 min"]].map(([k, label]) => (
              <button key={k} type="button" role="radio" aria-checked={time === k} className={time === k ? "is-on" : ""} onClick={() => setFilter({ time: k })}>{label}</button>
            ))}
          </div>
        </div>
      </div>
      <footer className="filters-footer">
        <button type="button" className="text-link" onClick={reset}>Clear all</button>
        <button type="button" className="filters-show" onClick={() => go("/recipes")}>
          Show meals
          <span>{filterCount === 0 ? "All" : filterCount === 1 ? "1 filter" : `${filterCount} filters`}</span>
        </button>
      </footer>
    </section>
  );
}

export function Social() {
  const [prefs, setPrefs] = useState({
    other_recipes: true,
    comments: true,
    other_photos: true,
  });
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .household()
      .then((hh) => {
        const s = hh.prefs?.social || {};
        setPrefs((cur) => ({ ...cur, ...s }));
      })
      .catch((e) => setErr(e.message));
  }, []);

  async function toggle(key) {
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next);
    try {
      const hh = await api.household();
      await api.putHousehold({ prefs: { ...(hh.prefs || {}), social: next } });
    } catch (e) {
      setErr(e.message);
    }
  }

  function row(key, label) {
    const on = !!prefs[key];
    return (
      <button type="button" className={`pref-row${on ? " is-on" : ""}`} onClick={() => toggle(key)}>
        <span>
          <strong>{label}</strong>
        </span>
        <em>{on ? "On" : "Off"}</em>
      </button>
    );
  }

  return (
    <section className="screen">
      <header className="top sub">
        <button type="button" className="icon-btn" onClick={() => go("/settings")} aria-label="Back">
          ←
        </button>
        <h1>Social</h1>
        <span />
      </header>
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        {row("other_recipes", "Recipes from other cooks")}
        {row("comments", "Comments & reviews")}
        {row("other_photos", "Photos from other cooks")}
      </div>
    </section>
  );
}

export function Newsletter() {
  const [on, setOn] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .household()
      .then((hh) => setOn(Boolean(hh.prefs?.newsletter)))
      .catch((e) => setErr(e.message));
  }, []);

  async function toggle() {
    const next = !on;
    setOn(next);
    setErr("");
    try {
      const hh = await api.household();
      await api.putHousehold({ prefs: { ...(hh.prefs || {}), newsletter: next } });
    } catch (e) {
      setOn(!next);
      setErr(e.message);
    }
  }

  return (
    <section className="screen">
      <header className="top sub">
        <button type="button" className="icon-btn" onClick={() => go("/settings")} aria-label="Back">
          ←
        </button>
        <h1>Email newsletter</h1>
        <span />
      </header>
      <div className="scroll pad">
        {err && <p className="banner err" role="alert">{err}</p>}
        <label className="pref-row">
          <span>
            <strong>Email newsletter</strong>
          </span>
          <input type="checkbox" id="email-newsletter" checked={on} onChange={toggle} />
        </label>
        <p className="help">
          We'll send you our intermittent newsletter 'DinnerDesk Deals' with ways to save money, latest recipes and tips. You can unsubscribe in one click, at any time.
        </p>
        <button type="button" className="btn-secondary block" onClick={toggle}>
          {on ? "Unsubscribe" : "Subscribe"}
        </button>
      </div>
    </section>
  );
}

export function AccountSecurity() {
  const [status, setStatus] = useState(null);
  const [members, setMembers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [toast, setToast] = useState("");
  const [householdName, setHouseholdName] = useState("");
  const [inviteLink, setInviteLink] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [joinToken, setJoinToken] = useState("");
  const [homePassword, setHomePassword] = useState("");
  const [deletingHome, setDeletingHome] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");

  useEffect(() => {
    api.auth
      .status()
      .then(setStatus)
      .catch((e) => setErr(e.message));
  }, []);

  useEffect(() => {
    if (status && status.authenticated) {
      api.household().then((household) => setHouseholdName(household.name)).catch((e) => setErr(e.message));
      api.householdMembers().then((r) => setMembers(r.members)).catch((e) => setErr(e.message));
    }
  }, [status]);

  async function saveHouseholdName(e) {
    e.preventDefault();
    if (!householdName.trim()) return;
    setBusy(true);
    setErr("");
    try {
      const household = await api.putHousehold({ name: householdName.trim() });
      setHouseholdName(household.name);
      setToast("Household name saved.");
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }

  async function emailResetLink() {
    setErr("");
    setBusy(true);
    try {
      await api.auth.forgotPassword({ email: status.email });
      setToast(`Reset link sent to ${status.email}. It works once, for 1 hour.`);
    } catch (e) {
      setErr((e.body && e.body.message) || e.message);
    } finally {
      setBusy(false);
    }
  }

  async function makeInvite() {
    setErr("");
    try {
      const { token } = await api.createHouseholdInvite();
      setInviteLink(`${window.location.origin}/join/${token}`);
    } catch (e) {
      setErr((e.body && e.body.message) || e.message);
    }
  }

  async function shareInvite() {
    try {
      if (navigator.share) {
        await navigator.share({ title: "Join my Dinnerdesk household", url: inviteLink });
      } else { await copyInvite(); }
    } catch (e) { if (e.name !== "AbortError") setErr(e.message); }
  }

  async function copyInvite() {
    await navigator.clipboard.writeText(inviteLink);
    setToast("Invite link copied.");
  }

  async function householdAction(action) {
    setErr(""); setBusy(true);
    try { await action(); window.location.assign("/settings/account"); }
    catch (e) { setErr((e.body && e.body.message) || e.message); }
    finally { setBusy(false); }
  }

  async function removeMember(id) {
    if (!confirm("Remove this person from the household? They'll lose access immediately.")) return;
    try {
      await api.removeHouseholdMember(id);
      setMembers((cur) => cur.filter((m) => m.id !== id));
    } catch (e) {
      setErr((e.body && e.body.message) || e.message);
    }
  }

  async function signOut() {
    await api.auth.logout();
    go("/login");
  }

  async function signOutEverywhere() {
    if (!confirm("Sign out of every device signed in to this account?")) return;
    await api.auth.logoutEverywhere();
    go("/login");
  }

  async function deleteAccount(e) {
    e.preventDefault();
    if (!deletePassword) return;
    setErr("");
    setBusy(true);
    try {
      await api.auth.deleteAccount({ password: deletePassword });
      go("/login");
    } catch (e) {
      setErr((e.body && e.body.message) || e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!status) return null;
  const myRole = members.find((m) => m.email === status.email)?.household_role;
  const canManage = ["owner", "admin"].includes(myRole);
  const alone = members.filter((m) => m.email !== status.email).length === 0;

  return (
    <section className="screen">
      <header className="top sub">
        <button type="button" className="icon-btn" onClick={() => go("/settings")} aria-label="Back">
          ←
        </button>
        <h1>Account &amp; security</h1>
        <span />
      </header>
      <div className="scroll pad">
        {toast ? <p className="banner ok">{toast}</p> : null}
        {err ? <p className="banner err">{err}</p> : null}

        {!status.authenticated ? (
          <>
            <p className="help">You're not signed in to an account yet.</p>
            <button type="button" className="btn-primary block" onClick={() => go("/login")}>
              Sign in or create an account
            </button>
          </>
        ) : (
          <>
            <label className="block-label">Signed in as</label>
            <p>{status.email}</p>

            <form onSubmit={saveHouseholdName}>
              <label className="block-label" htmlFor="household-name">Household name</label>
              <input className="field" id="household-name" value={householdName} maxLength={80} onChange={(e) => setHouseholdName(e.target.value)} required />
              <button type="submit" className="btn-secondary block" disabled={busy || !householdName.trim()}>Save household name</button>
            </form>
            <label className="block-label">Household members</label>
            {members.filter((m) => m.email !== status.email).map((m) => (
              <div key={m.id} className="list-link">
                <span>{m.email} · {m.household_role}</span>
                {myRole === "owner" && <>
                  <button className="btn-secondary" disabled={busy} onClick={() => { if (confirm("Make this member the household creator? You become an admin.")) householdAction(() => api.householdRole(m.id, "owner")); }}>Transfer ownership</button>
                  <button className="btn-secondary" disabled={busy} onClick={() => householdAction(() => api.householdRole(m.id, m.household_role === "admin" ? "member" : "admin"))}>{m.household_role === "admin" ? "Remove admin role" : "Make admin"}</button>
                </>}
                {canManage && m.household_role !== "owner" && (
                  <button
                    type="button"
                    className="icon-btn"
                    onClick={() => removeMember(m.id)}
                    aria-label="Remove"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
            <button type="button" className="btn-secondary block" onClick={makeInvite}>
              Invite someone to this household
            </button>
            {inviteLink && (
              <>
                <Tip id="settings.invite-link">
                  Share this link — whoever opens it and creates an account joins your household
                  and sees the same recipes, plan, and grocery list. Expires in 7 days, one-time use.
                </Tip>
                <input className="field" readOnly value={inviteLink} onFocus={(e) => e.target.select()} />
                <button type="button" className="btn-secondary block" onClick={shareInvite}>
                  Copy link
                </button>
              </>
            )}

            {status.has_email === false ? (
              <p className="help">This account has a username instead of an email, so there's no reset link. If you forget your password, the account can't be recovered.</p>
            ) : (
              <>
                <button type="button" className="btn-secondary block" disabled={busy} onClick={emailResetLink}>
                  Reset password
                </button>
                <p className="help">Email a reset link to your signed-in address.</p>
              </>
            )}

            <label className="block-label">Sessions</label>
            <button type="button" className="btn-secondary block" onClick={signOut}>
              Sign out
            </button>
            <button type="button" className="btn-secondary block" onClick={signOutEverywhere}>
              Sign out everywhere
            </button>
            <Tip id="settings.sign-out-everywhere">
              Signs out every device using this account — use this if a phone or laptop was lost
              or you just changed your password and want to be sure.
            </Tip>

            <label className="block-label">Household membership</label>
            <p className="help">Leaving creates an empty solo household. Your account stays active. Shared plans and kitchen data stay with the household.</p>
            <button className="btn-secondary block" disabled={busy} onClick={() => { if (confirm("Leave this household and start an empty solo household?")) householdAction(() => api.leaveHousehold()); }}>Leave household</button>
            <label className="block-label" htmlFor="join-household">Join with an invite link or token</label>
            <input id="join-household" className="field" value={joinToken} onChange={(e) => setJoinToken(e.target.value)} />
            <button className="btn-secondary block" disabled={busy || !joinToken.trim()} onClick={() => { if (confirm("Join this household? Your current solo kitchen will be removed; shared kitchens remain for their members.")) householdAction(() => api.joinHousehold(joinToken.trim().split("/").pop())); }}>Join household</button>
            {canManage && <>
              <button className="btn-secondary block danger" onClick={() => setDeletingHome(!deletingHome)}>Delete household</button>
              {deletingHome && <>
                <p className="help">Permanently removes this shared kitchen and its plans. Everyone keeps their account and receives an empty solo household. Anonymous meal votes are retained.</p>
                <input className="field" type="password" autoComplete="current-password" aria-label="Password to delete household" value={homePassword} onChange={(e) => setHomePassword(e.target.value)} />
                <button className="btn-secondary block danger" disabled={busy || !homePassword} onClick={() => householdAction(() => api.deleteHousehold(homePassword))}>Confirm household deletion</button>
              </>}
            </>}
            <label className="block-label">Delete account</label>
            {!deleting ? (
              <button type="button" className="btn-secondary block danger" onClick={() => setDeleting(true)}>
                Delete account
              </button>
            ) : (
              <form onSubmit={deleteAccount}>
                <p className="help">Anonymous meal votes are retained without account identifiers.</p>
                <p className="help">
                  {alone
                    ? "This deletes your account and everything in this household: plans, pantry, grocery list, ratings and recipes you added. It can’t be undone."
                    : "This deletes your account and your sign-ins. The household and its plans stay for the other members."}
                </p>
                <label className="block-label" htmlFor="delete-password">Your password</label>
                <input className="field" id="delete-password" type="password" autoComplete="current-password"
                  value={deletePassword} onChange={(e) => setDeletePassword(e.target.value)} required />
                <button type="submit" className="btn-secondary block danger" disabled={busy || !deletePassword}>
                  Delete my account
                </button>
                <button type="button" className="btn-secondary block" onClick={() => { setDeleting(false); setDeletePassword(""); }}>
                  Cancel
                </button>
              </form>
            )}
          </>
        )}
      </div>
    </section>
  );
}
