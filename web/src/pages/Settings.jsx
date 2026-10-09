import { useEffect, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";
import { ALLERGENS, AVOIDS, DIETS, cleanDiets, otherWords, toggleAvoid, toggleDiet } from "../diet.js";

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
        <p className="help" data-tip="settings.gold-star">
          A gold ★ means we (Dinnerdesk) have reviewed and tested the recipe. Only we
          can add that mark. It’s there so you can see which recipes we definitively trust. Other
          recipes still come from trusted sources; their photos are public-use or AI-generated. Real photos are updated as we test recipes.
        </p>
      </div>
    </section>
  );
}

const TIMES = [
  ["any", "Any"],
  ["30", "≤30 min"],
  ["45", "≤45 min"],
];

/** Chips for a list plus an Other box for words not on it. Saves the whole list. */
function FoodFilterPicker({ label, selected, onAdd, onRemove }) {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setMatches([]);
    setError("");
    setLoading(Boolean(query.trim()));
    if (!query.trim()) return;
    const timer = setTimeout(() => api.filterItems(query)
      .then((box) => { if (active) setMatches(box.items.map((item) => item.name)); })
      .catch(() => { if (active) setError("Couldn't search foods. Please try again."); })
      .finally(() => { if (active) setLoading(false); }), 250);
    return () => { active = false; clearTimeout(timer); };
  }, [query]);
  return <div className="filter-food-picker">
    <div className="chip-row wrap">{selected.map((name) => <button type="button" className="chip is-on" key={name} aria-label={`Remove ${name}`} onClick={() => onRemove(name)}>{name} ×</button>)}</div>
    <label className="block-label">{label}<input className="field" aria-label={`Search ${label.toLowerCase()}`} placeholder="Search foods, e.g. bell peppers or ground" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
    {loading && <p role="status">Searching…</p>}
    {error && <p role="alert">{error}</p>}
    <div className="filter-food-results">{matches.filter((name) => !selected.includes(name)).map((name) => <button type="button" className="list-link" key={name} onClick={() => { onAdd(name); setQuery(""); }}>{name}</button>)}</div>
    {!loading && !error && query.trim() && !matches.length && <p role="status">No matching foods. Try another name.</p>}
  </div>;
}

function ChoiceBlock({ label, items, saved, onChange, otherLabel }) {
  const custom = otherWords(saved, items);
  const [open, setOpen] = useState(custom.length > 0);
  useEffect(() => { if (custom.length) setOpen(true); }, [custom.join("\u001f")]);
  return (
    <>
      <h3 className="block-label">{label}</h3>
      <div className="chip-row wrap">
        <button type="button" className={`chip${saved.length ? "" : " is-on"}`} aria-pressed={!saved.length} onClick={() => { setOpen(false); onChange([]); }}>
          none
        </button>
        {items.map((item) => {
          const [id, text] = Array.isArray(item) ? item : [item, item];
          const on = saved.includes(id);
          return (
            <button key={id} type="button" className={`chip${on ? " is-on" : ""}`} aria-pressed={on} onClick={() => onChange(toggleAvoid(saved, id))}>
              {text.toLowerCase()}
            </button>
          );
        })}
        <button type="button" className={`chip${open || custom.length ? " is-on" : ""}`} aria-expanded={open} onClick={() => setOpen(!open)}>
          other…
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
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .household()
      .then((hh) => {
        const f = hh.prefs?.filters || {};
        if (Array.isArray(f.diets)) setDiets(cleanDiets(f.diets));
        if (Array.isArray(f.allergens)) setAllergens(f.allergens);
        if (Array.isArray(f.avoids)) setAvoids(f.avoids);
        if (f.time) setTime(f.time);
      })
      .catch((e) => setErr(e.message));
  }, []);

  // The server merges filters, so send only what changed.
  async function setFilter(patch) {
    if (patch.diets) setDiets(patch.diets);
    if (patch.allergens) setAllergens(patch.allergens);
    if (patch.avoids) setAvoids(patch.avoids);
    if (patch.time) setTime(patch.time);
    try {
      await api.putHousehold({ prefs: { filters: patch } });
      setErr("");
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <section className="screen">
      <header className="top sub">
        <button type="button" className="icon-btn" onClick={() => go("/settings")} aria-label="Back">
          ←
        </button>
        <h1>Filters</h1>
        <span />
      </header>
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        <p className="help">Recipes, suggestions and Taste Lab all use these. Changing them in Taste Lab changes them here.</p>
        <h3 className="block-label">Diet</h3>
        <div className="chip-row wrap">
          {DIETS.map((d) => (
            <button
              key={d}
              type="button"
              className={`chip${diets.includes(d) ? " is-on" : ""}`}
              aria-pressed={diets.includes(d)}
              onClick={() => setFilter({ diets: toggleDiet(diets, d) })}
            >
              {d}
            </button>
          ))}
        </div>
        <ChoiceBlock label="Allergies" items={ALLERGENS} saved={allergens} otherLabel="Other allergies" onChange={(next) => setFilter({ allergens: next })} />
        <ChoiceBlock label="Avoid" items={AVOIDS} saved={avoids} otherLabel="Other foods to avoid" onChange={(next) => setFilter({ avoids: next })} />
        <h3 className="block-label">Time</h3>
        <div className="chip-row wrap">
          {TIMES.map(([k, label]) => (
            <button
              key={k}
              type="button"
              className={`chip${time === k ? " is-on" : ""}`}
              aria-pressed={time === k}
              onClick={() => setFilter({ time: k })}
            >
              {label}
            </button>
          ))}
        </div>
        <button type="button" className="btn-primary block" onClick={() => go("/recipes")}>
          Show recipes
        </button>
      </div>
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
                <span>{m.email}</span>
                {members.length > 1 && (
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
                <p className="help" data-tip="settings.invite-link">
                  Share this link — whoever opens it and creates an account joins your household
                  and sees the same recipes, plan, and grocery list. Expires in 7 days, one-time use.
                </p>
                <input className="field" readOnly value={inviteLink} onFocus={(e) => e.target.select()} />
                <button type="button" className="btn-secondary block" onClick={shareInvite}>
                  Copy link
                </button>
              </>
            )}

            <button type="button" className="btn-secondary block" disabled={busy} onClick={emailResetLink}>
              Reset password
            </button>
            <p className="help">Email a reset link to your signed-in address.</p>

            <label className="block-label">Sessions</label>
            <button type="button" className="btn-secondary block" onClick={signOut}>
              Sign out
            </button>
            <button type="button" className="btn-secondary block" onClick={signOutEverywhere}>
              Sign out everywhere
            </button>
            <p className="help" data-tip="settings.sign-out-everywhere">
              Signs out every device using this account — use this if a phone or laptop was lost
              or you just changed your password and want to be sure.
            </p>

            <label className="block-label">Delete account</label>
            {!deleting ? (
              <button type="button" className="btn-secondary block danger" onClick={() => setDeleting(true)}>
                Delete account
              </button>
            ) : (
              <form onSubmit={deleteAccount}>
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
