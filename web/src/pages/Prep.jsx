import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";
import { Thumbs } from "../Thumbs.jsx";
import { Icon } from "../icons.jsx";
import "./prep.css";

/* Weekend prep, grouped by what the food is (#21): one row per item however many meals use it,
   a progress ring plus one bar per section, collapsible sections, thumbs up/down on every item, and
   check-off that works like the grocery list (done items leave unless "Show completed"). */

const SECTIONS = [
  ["veg", "Vegetables", "Veg"],
  ["herbs", "Aromatics, herbs & citrus", "Aromatics"],
  ["protein", "Protein", "Protein"],
  ["cheese", "Cheese & dairy", "Cheese"],
  ["sauce", "Sauces & dressings", "Sauce"],
  ["other", "More prep", "More"],
];
export const PREP_REASONS = [
  ["day_of", "Better done day-of"],
  ["kept_badly", "Didn’t keep well"],
  ["too_small", "Too small to bother"],
  ["prep_differently", "Prep it differently"],
  ["not_prep", "Not a prep step"],
];
const reasonLabel = (id) => PREP_REASONS.find(([key]) => key === id)?.[1] || "";

const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem(key); return v == null ? fallback : JSON.parse(v); } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private window */ }
  },
};

export function Prep() {
  const [tasks, setTasks] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [err, setErr] = useState("");
  const [showDone, setShowDone] = useState(() => store.get("prep.showDone", false));
  const [closed, setClosed] = useState(() => new Set(store.get("prep.closed", [])));
  const [why, setWhy] = useState(null); // task id whose "Why not?" is open
  const [open, setOpen] = useState(() => new Set()); // rows showing their per-meal steps
  const [toast, setToast] = useState(null); // { id, why }

  async function load() {
    const plan = await api.plan();
    const data = await api.prep(plan.id);
    setTasks(data.tasks);
    setLoaded(true);
  }

  useEffect(() => {
    load().catch((e) => { setErr(e.message); setLoaded(true); });
  }, []);

  const patchLocal = (id, change) => setTasks((cur) => cur.map((t) => (t.id === id ? { ...t, ...change } : t)));

  async function toggle(task) {
    const done = !task.done;
    patchLocal(task.id, { done });
    setToast(done ? { id: task.id, why: false } : null);
    try {
      await api.patchPrep(task.id, done);
    } catch (e) {
      setErr(e.message);
      load();
    }
  }

  async function rate(task, rating, reason = "") {
    const before = { rating: task.rating || 0, reason: task.reason || "" };
    patchLocal(task.id, { rating, reason: rating < 0 ? reason : "" });
    try {
      await api.ratePrepTask(task.id, { rating, reason: rating < 0 ? reason : "" });
    } catch (e) {
      patchLocal(task.id, before);
      setErr(e.message);
    }
  }

  function thumbsOnRow(task, next) {
    rate(task, next, next < 0 ? task.reason : "");
    setWhy(next < 0 ? task.id : null);
  }

  function toggleSection(key) {
    const next = new Set(closed);
    if (next.has(key)) next.delete(key); else next.add(key);
    setClosed(next);
    store.set("prep.closed", [...next]);
  }

  function toggleShowDone() {
    setShowDone(!showDone);
    store.set("prep.showDone", !showDone);
  }

  const total = tasks.length;
  const doneCount = tasks.filter((t) => t.done).length;
  const pct = total ? Math.round((100 * doneCount) / total) : 0;
  const sections = useMemo(
    () => SECTIONS.map(([key, title, short]) => {
      const all = tasks.filter((t) => (t.section || "other") === key);
      const done = all.filter((t) => t.done);
      const shown = showDone ? [...all.filter((t) => !t.done), ...done] : all.filter((t) => !t.done);
      return { key, title, short, all, done: done.length, shown };
    }).filter((s) => s.all.length),
    [tasks, showDone],
  );
  const toastTask = toast && tasks.find((t) => t.id === toast.id);

  return (
    <section className="screen prep-screen">
      <header className="top">
        <button type="button" className="icon-btn mob-back" onClick={() => go("/more")} aria-label="Back">
          ←
        </button>
        <h1>Weekend prep</h1>
      </header>
      <div className="scroll pad">
        {err && <p className="banner err" role="alert">{err}</p>}
        {loaded && total === 0 ? (
          <>
            <p className="muted" data-tip="prep.empty">No prep yet. Add meals on Plan. Make-ahead steps like chopping, grating and sauces show up here.</p>
            <button type="button" className="btn-secondary" onClick={() => go("/")}>
              Back to plan
            </button>
          </>
        ) : total > 0 && (
          <>
            <div className="pz-head">
              <div className="pz-ring" style={{ background: `conic-gradient(var(--coral) 0 ${pct}%, #f1e7ef ${pct}% 100%)` }}
                role="img" aria-label={`${doneCount} of ${total} prep items done`}>
                <span>{doneCount}/{total}</span>
              </div>
              <p className="help" data-tip="prep.about">Built from this plan’s meals. Chop and batch now; cook fresh later in the week.</p>
            </div>
            <nav className="pz-bars" aria-label="Jump to section">
              {sections.map((s) => (
                <a key={s.key} href={`#prep-${s.key}`} onClick={(e) => { e.preventDefault(); document.getElementById(`prep-${s.key}`)?.scrollIntoView({ block: "start" }); }}>
                  <span className="pz-bar"><span style={{ width: `${Math.round((100 * s.done) / s.all.length)}%` }} /></span>
                  <span className="pz-bar-label">{s.short} <span>{s.done}/{s.all.length}</span></span>
                </a>
              ))}
            </nav>
            <div className="pz-done-row">
              <span className="muted">{doneCount} completed</span>
              {doneCount > 0 && <button type="button" className="text-link" onClick={toggleShowDone}>{showDone ? "Hide completed" : "Show completed"}</button>}
            </div>

            {sections.map((s) => {
              const isOpen = !closed.has(s.key);
              return (
                <section key={s.key} id={`prep-${s.key}`} className="pz-section">
                  <h2>
                    <button type="button" className="pz-section-head" aria-expanded={isOpen} onClick={() => toggleSection(s.key)}>
                      <span className="pz-section-title">{s.title}</span>
                      <span className="muted">{s.done} of {s.all.length}</span>
                      <span className={`pz-arrow${isOpen ? "" : " is-closed"}`} aria-hidden="true">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 15l6-6 6 6" /></svg>
                      </span>
                    </button>
                  </h2>
                  {isOpen && (s.shown.length === 0
                    ? <p className="pz-empty">All prepped here.</p>
                    : <ul className="pz-card">
                      {s.shown.map((t) => (
                        <PrepRow key={t.id} task={t}
                          why={why === t.id} details={open.has(t.id)}
                          onToggle={() => toggle(t)}
                          onRate={(next) => thumbsOnRow(t, next)}
                          onReason={(reason) => { rate(t, -1, reason); setWhy(null); }}
                          onDetails={() => setOpen((cur) => { const n = new Set(cur); if (n.has(t.id)) n.delete(t.id); else n.add(t.id); return n; })} />
                      ))}
                    </ul>)}
                </section>
              );
            })}
            <MissingPrep onChange={() => load().catch((e) => setErr(e.message))} onError={setErr} />
            <button type="button" className="list-foot-link" onClick={() => window.print()}>
              Print prep
            </button>
          </>
        )}
      </div>

      {toastTask && (
        <div className="pz-toast" role="status">
          <div className="pz-toast-row">
            <span className="pz-toast-check" aria-hidden="true">✓</span>
            <strong>{toastTask.title} checked off</strong>
            <button type="button" className="pz-toast-link" onClick={() => { toggle(toastTask); setToast(null); }}>Undo</button>
            <button type="button" className="pz-toast-x" aria-label="Dismiss" onClick={() => setToast(null)}>✕</button>
          </div>
          <div className="pz-toast-row">
            <span className="pz-toast-q">Worth prepping ahead next time?</span>
            <button type="button" className="pz-toast-thumb" aria-pressed={toastTask.rating > 0} aria-label="Yes, worth it"
              onClick={() => { rate(toastTask, 1); setToast(null); }}><Icon name="thumbs-up" size={18} /></button>
            <button type="button" className="pz-toast-thumb" aria-pressed={toastTask.rating < 0} aria-label="No, not worth it"
              onClick={() => { rate(toastTask, -1, toastTask.reason); setToast({ id: toastTask.id, why: true }); }}><Icon name="thumbs-down" size={18} /></button>
          </div>
          {toast.why && (
            <div className="pz-chips">
              {PREP_REASONS.map(([id, label]) => (
                <button key={id} type="button" className="pz-toast-chip" aria-pressed={toastTask.reason === id}
                  onClick={() => { rate(toastTask, -1, id); setToast(null); }}>{label}</button>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function PrepRow({ task: t, why, details, onToggle, onRate, onReason, onDetails }) {
  const sub = (t.quantities || []).filter(Boolean).join(" · ");
  // Each different step once, with the meals that use it as light pill links (#78 D).
  const groups = [];
  for (const meal of t.meals || []) {
    for (const text of meal.steps?.length ? meal.steps.map((s) => s.text) : meal.instructions || []) {
      const hit = groups.find((g) => g.text.toLowerCase() === text.trim().toLowerCase());
      if (hit) { if (!hit.meals.some((m) => m.id === meal.id)) hit.meals.push(meal); }
      else groups.push({ text: text.trim(), meals: [meal] });
    }
  }
  return (
    <li className={`pz-item${t.done ? " is-done" : ""}${details ? " is-open" : ""}`}>
      <div className="pz-row">
        <button type="button" role="checkbox" aria-checked={t.done} className={`pz-check${t.done ? " on" : ""}`}
          aria-label={`${t.done ? "Uncheck" : "Check off"} ${t.title}`} onClick={onToggle}>
          {t.done ? "✓" : ""}
        </button>
        <button type="button" className="pz-text" aria-expanded={details} onClick={onDetails}>
          <span className="pz-name">{t.title}</span>
          {sub && <span className="pz-sub">{sub}</span>}
        </button>
        {/* 👍/👎 only on the open item (#78 D). */}
        {details && <Thumbs size={18} rating={t.rating || 0} subject={`prepping ${t.title} ahead`} onRate={onRate} />}
        <button type="button" className={`pz-chevron${details ? " on" : ""}`} aria-expanded={details}
          aria-label={`${details ? "Hide" : "Show"} steps for ${t.title}`} onClick={onDetails}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
        </button>
      </div>
      {t.rating < 0 && t.reason && !why && <div className="pz-indent"><span className="pz-tag">{reasonLabel(t.reason)}</span></div>}
      {why && (
        <div className="pz-indent pz-why">
          <span className="pz-why-q">Why not?</span>
          <div className="pz-chips">
            {PREP_REASONS.map(([id, label]) => (
              <button key={id} type="button" className="pz-chip" aria-pressed={t.reason === id} onClick={() => onReason(id)}>{label}</button>
            ))}
          </div>
        </div>
      )}
      {details && (
        <div className="pz-details">
          {groups.map((g, i) => (
            <div key={i} className="pz-step-group">
              <span className="pz-day" aria-hidden={!g.meals[0]?.day}>{g.meals[0]?.day || ""}</span>
              <div className="pz-step-body">
                <p className="pz-step">{g.text}</p>
                {g.meals.some((m) => m.steps?.some((st) => st.added && st.text.trim() === g.text)) && <span className="pz-added">Added by you</span>}
                {g.meals.map((meal) => (
                  <button key={meal.id} type="button" className="pz-pill" onClick={() => go(`/recipes/${meal.id}`)}
                    aria-label={`${meal.name}${meal.day ? `, ${meal.day}` : ""}: open recipe`}>
                    <span>{meal.name}</span>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </li>
  );
}

/* "Missing a prep step?" (#78 E/F): pick the meal, then the step that should have been prep,
   optionally say why, and it joins prep (and is logged for review). */
function MissingPrep({ onChange, onError }) {
  const [open, setOpen] = useState(false);
  const [meals, setMeals] = useState(null);
  const [mealId, setMealId] = useState(null);
  const [stepKey, setStepKey] = useState(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [added, setAdded] = useState(null); // { meal, text }

  const meal = meals?.find((m) => m.id === mealId);
  const step = meal?.steps.find((s) => s.key === stepKey);

  async function openPanel() {
    setOpen(!open);
    if (open || meals) return;
    try {
      const plan = await api.plan();
      setMeals((await api.missingPrep(plan.id)).meals);
    } catch (e) {
      onError(e.message);
      setOpen(false);
    }
  }

  function pickMeal(id) { setMealId(id); setStepKey(null); setNote(""); }

  async function save(m, st, adding) {
    setSaving(true);
    const text = adding ? note.trim() : "";
    try {
      const plan = await api.plan();
      await api.setMissingPrep(plan.id, { recipe_id: m.id, key: st.key, note: text, added: adding });
      setMeals((cur) => cur.map((x) => (x.id !== m.id ? x : {
        ...x, steps: x.steps.map((y) => (y.key === st.key ? { ...y, added: adding, note: text } : y)),
      })));
      if (adding) setAdded({ meal: m.name, text: st.text });
      setStepKey(null);
      setNote("");
      onChange();
    } catch (e) {
      onError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="pz-missing">
      <button type="button" className="pz-missing-open" aria-expanded={open} onClick={openPanel}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="10" /><path d="M12 8v8M8 12h8" /></svg>
        <span>
          <span className="pz-missing-title">Missing a prep step?</span>
          <span className="muted">Pick a step from this week’s recipes.</span>
        </span>
      </button>
      {open && (
        <div className="pz-missing-body">
          <p className="help">Tell us a step that would have saved time if you did it ahead. We’ll add it to your prep and use it to make prep better.</p>
          {meals == null ? <p className="muted">Loading…</p> : added ? (
            <div className="pz-missing-done" role="status">
              <span className="pz-missing-tick" aria-hidden="true">✓</span>
              <strong>Added to your prep</strong>
              <span>{added.text}</span>
              <span className="muted">{added.meal} · marked “Added by you”</span>
              <div className="pz-missing-actions">
                <button type="button" className="btn-secondary" onClick={() => { setAdded(null); pickMeal(null); }}>Add another</button>
                <button type="button" className="btn-primary" onClick={() => { setAdded(null); pickMeal(null); setOpen(false); }}>Done</button>
              </div>
            </div>
          ) : meals.length === 0 ? <p className="muted">Every step of this week’s recipes is already in prep.</p> : (
            <>
              <h3 className="pz-missing-label">1 · Meal</h3>
              {meal ? (
                <div className="pz-missing-picked">
                  <span className="pz-day">{meal.day || ""}</span>
                  <strong>{meal.name}</strong>
                  <button type="button" className="text-link" onClick={() => pickMeal(null)}>Change</button>
                </div>
              ) : (
                <ul className="pz-missing-meals">
                  {meals.map((m) => (
                    <li key={m.id}>
                      <button type="button" onClick={() => pickMeal(m.id)}>
                        <span className="pz-day">{m.day || ""}</span>
                        <span className="pz-missing-meal-text">
                          <strong>{m.name}</strong>
                          <span className="muted">{m.steps.length === 1 ? "1 step not in prep" : `${m.steps.length} steps not in prep`}</span>
                        </span>
                        <span aria-hidden="true">›</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {meal && (
                <>
                  <h3 className="pz-missing-label">2 · Step that should be prep</h3>
                  <div className="pz-missing-steps" role="radiogroup" aria-label="Step that should be prep">
                    {meal.steps.map((st) => st.added ? (
                      <div key={st.key} className="pz-missing-step is-added">
                        <span className="muted">Step {st.step} · in your prep{st.note ? ` · ${st.note}` : ""}</span>
                        <span>{st.text}</span>
                        <button type="button" className="text-link" disabled={saving} onClick={() => save(meal, st, false)}>Remove from prep</button>
                      </div>
                    ) : (
                      <button key={st.key} type="button" role="radio" aria-checked={st.key === stepKey}
                        className={`pz-missing-step${st.key === stepKey ? " is-picked" : ""}`} onClick={() => setStepKey(st.key)}>
                        <span className="pz-radio" aria-hidden="true" />
                        <span><span className="muted">Step {st.step}</span><span>{st.text}</span></span>
                      </button>
                    ))}
                  </div>
                </>
              )}
              {meal && step && (
                <div className="pz-missing-form">
                  <h3 className="pz-missing-label"><label htmlFor="pz-missing-note">3 · Why do it ahead? (optional)</label></h3>
                  <textarea id="pz-missing-note" rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)}
                    placeholder="e.g. Tofu needs 15 min to press — no time on a weeknight" />
                  <button type="button" className="btn-primary" disabled={saving} onClick={() => save(meal, step, true)}>{saving ? "Adding…" : "Add to prep"}</button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}
