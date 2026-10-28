import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";
import { Icon } from "../icons.jsx";
import "./prep.css";

/* Weekend prep, grouped by what the food is (#21): one row per item however many meals use it,
   one progress bar, and check-off that works like the grocery list (done items leave unless
   "Show completed"). One item is open at a time (prep.html, #220): its steps, the meals it's for,
   Done / Skip (both move on to the next item) and "Worth prepping ahead?". */

const SECTIONS = [
  ["veg", "Vegetables"],
  ["herbs", "Aromatics, herbs & citrus"],
  ["protein", "Protein"],
  ["cheese", "Cheese & dairy"],
  ["sauce", "Sauces & dressings"],
  ["other", "More prep"],
];
export const PREP_REASONS = [
  ["day_of", "Better done day-of"],
  ["kept_badly", "Didn’t keep well"],
  ["too_small", "Too small to bother"],
  ["prep_differently", "Prep it differently"],
  ["not_prep", "Not a prep step"],
];

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
  const [openId, setOpenId] = useState(null); // the one item showing its steps
  const [report, setReport] = useState(null); // task id whose "What's wrong?" box is open
  const [menu, setMenu] = useState(false);
  const [toast, setToast] = useState(null); // { id, why }

  async function load() {
    const plan = await api.plan();
    const data = await api.prep(plan.id);
    setTasks(data.tasks);
    setOpenId((cur) => cur ?? data.tasks.find((t) => !t.done)?.id ?? null);
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

  async function rate(task, rating, reason = "", note = task.reason_note || "") {
    const before = { rating: task.rating || 0, reason: task.reason || "", reason_note: task.reason_note || "" };
    const down = rating < 0;
    patchLocal(task.id, { rating, reason: down ? reason : "", reason_note: down ? note : "" });
    try {
      await api.ratePrepTask(task.id, { rating, reason: down ? reason : "", note: down ? note : "" });
    } catch (e) {
      patchLocal(task.id, before);
      setErr(e.message);
    }
  }

  // Items in the order they're listed, for Done / Skip moving on.
  const order = SECTIONS.flatMap(([key]) => tasks.filter((t) => (t.section || "other") === key));
  function openNext(task) {
    const i = order.findIndex((t) => t.id === task.id);
    const next = [...order.slice(i + 1), ...order.slice(0, i)].find((t) => !t.done);
    setOpenId(next ? next.id : null);
    setReport(null);
  }
  function check(task) {
    toggle(task);
    if (!task.done && openId === task.id) openNext(task);
  }

  function toggleShowDone() {
    setShowDone(!showDone);
    store.set("prep.showDone", !showDone);
  }

  const total = tasks.length;
  const doneCount = tasks.filter((t) => t.done).length;
  const pct = total ? Math.round((100 * doneCount) / total) : 0;
  const sections = useMemo(
    () => SECTIONS.map(([key, title]) => {
      const all = tasks.filter((t) => (t.section || "other") === key);
      const done = all.filter((t) => t.done);
      const shown = showDone ? [...all.filter((t) => !t.done), ...done] : all.filter((t) => !t.done);
      return { key, title, all, done: done.length, shown };
    }).filter((s) => s.all.length),
    [tasks, showDone],
  );
  const toastTask = toast && tasks.find((t) => t.id === toast.id);

  return (
    <section className="screen narrow col-720 prep-screen">
      <header className="top page-top">
        <button type="button" className="icon-btn mob-back" onClick={() => go("/more")} aria-label="Back">
          ←
        </button>
        <h1>Weekend prep</h1>
        {total > 0 && (
          <button type="button" className="more-btn" aria-label="More options" aria-expanded={menu} onClick={() => setMenu(!menu)}>
            <Icon name="dots" size={24} />
          </button>
        )}
      </header>
      {menu && (
        <div className="action-sheet prep-options">
          {doneCount > 0 && <button type="button" onClick={() => { toggleShowDone(); setMenu(false); }}>{showDone ? "Hide completed" : `Show completed (${doneCount})`}</button>}
          <button type="button" onClick={() => { setMenu(false); window.print(); }}>Print prep</button>
          <button type="button" onClick={() => setMenu(false)}>Done</button>
        </div>
      )}
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
            <p className="pz-progress-text" data-tip="prep.about"><strong>{doneCount} of {total} done.</strong> Chop and batch now; cook fresh later in the week.</p>
            <div className="pz-progress" role="progressbar" aria-label="Prep progress" aria-valuemin={0} aria-valuemax={total} aria-valuenow={doneCount}>
              <div style={{ width: `${pct}%` }} />
            </div>

            {sections.map((s) => (
              <section key={s.key} id={`prep-${s.key}`} className="pz-section">
                <h2 className="pz-group-label"><span>{s.title}</span><span>{s.done} of {s.all.length}</span></h2>
                {s.shown.length === 0
                  ? <p className="pz-empty">All prepped here.</p>
                  : s.shown.map((t) => (
                    <PrepRow key={t.id} task={t} open={openId === t.id} reporting={report === t.id}
                      onCheck={() => check(t)}
                      onOpen={() => { setOpenId(openId === t.id ? null : t.id); setReport(null); }}
                      onDone={() => { if (!t.done) toggle(t); openNext(t); }}
                      onSkip={() => openNext(t)}
                      onRate={(next) => { rate(t, next, next < 0 ? t.reason : ""); setReport(next < 0 ? t.id : null); }}
                      onReport={() => setReport(report === t.id ? null : t.id)}
                      onSend={(note) => { rate(t, -1, t.reason || "", note); setReport(null); }} />
                  ))}
              </section>
            ))}
            <MissingPrep onChange={() => load().catch((e) => setErr(e.message))} onError={setErr} />
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

function PrepRow({ task: t, open, reporting, onCheck, onOpen, onDone, onSkip, onRate, onReport, onSend }) {
  const [note, setNote] = useState(t.reason_note || "");
  const amount = (t.quantities || []).filter(Boolean).join(" · ");
  // Each different step once (several meals often share the same words).
  const how = [];
  for (const meal of t.meals || []) {
    for (const text of meal.steps?.length ? meal.steps.map((s) => s.text) : meal.instructions || []) {
      if (!how.some((h) => h.text.toLowerCase() === text.trim().toLowerCase())) {
        how.push({ text: text.trim(), added: Boolean(meal.steps?.some((st) => st.added && st.text.trim() === text.trim())) });
      }
    }
  }
  return (
    <div className={`pz-step-item${open ? " open" : ""}${t.done ? " done" : ""}`}>
      <div className="pz-step-head">
        <button type="button" className="pz-check" aria-label={`${t.done ? "Mark not done" : "Mark done"}: ${t.title}`} onClick={onCheck}>
          {t.done && <Icon name="check" size={13} />}
        </button>
        <button type="button" className="pz-toggle" aria-expanded={open} aria-controls={`pz-step-${t.id}`} onClick={onOpen}>
          <span className="pz-title">{t.title}</span>
          {amount && <span className="pz-amount">{amount}</span>}
          <span className="pz-chev" aria-hidden="true"><Icon name="chevron-down" size={14} /></span>
        </button>
      </div>
      {open && (
        <div className="pz-step-body" id={`pz-step-${t.id}`}>
          {how.map((h, i) => (
            <p key={i} className="pz-how">{h.text}{h.added && <span className="pz-added">Added by you</span>}</p>
          ))}
          {t.meals?.length > 0 && (
            <div>
              <p className="pz-meals-label">{t.meals.length > 1 ? "Split between" : "For"}</p>
              {t.meals.map((meal) => (
                <a key={meal.id} className="pz-meal-link" href={`/recipes/${meal.id}`} onClick={(e) => { e.preventDefault(); go(`/recipes/${meal.id}`); }}>
                  <span className="pz-meal-name">{meal.name}</span>
                  {meal.day && <span className="pz-meal-day">{meal.day}</span>}
                </a>
              ))}
            </div>
          )}
          <div className="pz-actions">
            <button type="button" className="pz-btn-done" onClick={onDone}>Done</button>
            <button type="button" className="pz-btn-skip" onClick={onSkip}>Skip</button>
          </div>
          <div className="pz-feedback">
            <span className="pz-feedback-q">Worth prepping ahead?</span>
            <button type="button" className="pz-fb-btn" aria-label="Yes, worth it" aria-pressed={t.rating > 0} onClick={() => onRate(t.rating > 0 ? 0 : 1)}>
              <Icon name="thumbs-up" size={18} />
            </button>
            <button type="button" className="pz-fb-btn" aria-label="No, not worth it" aria-pressed={t.rating < 0} onClick={() => onRate(t.rating < 0 ? 0 : -1)}>
              <Icon name="thumbs-down" size={18} />
            </button>
            <button type="button" className="pz-fb-btn" aria-label="Report a problem or send feedback" aria-expanded={reporting} onClick={onReport}>
              <Icon name="flag" size={18} />
            </button>
          </div>
          {reporting && (
            <div className="pz-report">
              <label htmlFor={`pz-report-${t.id}`}>What's wrong with this step?</label>
              <textarea id={`pz-report-${t.id}`} rows={2} maxLength={500} value={note}
                placeholder="Wrong amount, unclear step, missing ingredient…" onChange={(e) => setNote(e.target.value)} />
              <button type="button" onClick={() => onSend(note.trim())}>Send feedback</button>
            </div>
          )}
        </div>
      )}
    </div>
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
