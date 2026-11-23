import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";
import { Icon } from "../icons.jsx";
import { PREP_REASONS } from "../reportOptions.js";
export { PREP_REASONS } from "../reportOptions.js";
import { PrepTaskPresentation, prepMealGroups } from "../PrepTaskPresentation.js";
import "./prep.css";
import { Copy } from "../Copy.js";

/* Weekend prep, grouped by what the food is (#21): one row per item however many meals use it,
   one progress bar, and check-off that works like the grocery list (done items leave unless
   Copy.text("ui.show.completed")). One item is open at a time (prep.html, #220): its steps, the meals it's for,
   Done / Skip (both move on to the next item) and "Worth prepping ahead?".
   Copy.text("ui.by.meal") shows the same work under each meal: one row per task with a progress ring
   (checks off that meal's steps only), a one-line summary, and the steps folded out. */

const SECTIONS = [
  ["veg", "Vegetables"],
  ["herbs", "Aromatics, herbs & citrus"],
  ["protein", "Protein"],
  ["cheese", "Cheese & dairy"],
  ["sauce", "Sauces & dressings"],
  ["other", Copy.text("ui.more.prep")],
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
  const [mealGroups, setMealGroups] = useState([]);
  const [view, setView] = useState(() => store.get("prep.view", "meal")); // "meal" | "task"
  const [openMealTask, setOpenMealTask] = useState(null); // "mealId:taskId" open in By meal

  async function load() {
    const plan = await api.plan();
    const data = await api.prep(plan.id);
    setTasks(data.tasks);
    setMealGroups(prepMealGroups(data));
    setOpenId((cur) => cur ?? data.tasks.find((t) => !t.done)?.id ?? null);
    setLoaded(true);
  }

  useEffect(() => {
    load().catch((e) => { setErr(e.message); setLoaded(true); });
  }, []);

  const patchLocal = (id, change) => setTasks((cur) => cur.map((t) => (t.id === id ? { ...t, ...change } : t)));

  // Keep both views in step after a check: the task's steps and the by-meal copies.
  function markSteps(taskId, mealId, keys, done) {
    const hit = (meal, step) => (mealId == null || meal === mealId) && (keys == null || keys.includes(step.key));
    setTasks((cur) => cur.map((t) => {
      if (t.id !== taskId) return t;
      const meals = (t.meals || []).map((m) => ({ ...m, steps: (m.steps || []).map((st) => (hit(m.id, st) ? { ...st, done } : st)) }));
      const steps = meals.flatMap((m) => m.steps);
      return { ...t, meals, done: steps.length ? steps.every((st) => st.done) : done };
    }));
    setMealGroups((cur) => cur.map((g) => ({
      ...g,
      tasks: g.tasks.map((t) => {
        if (t.task_id !== taskId) return t;
        const steps = t.steps.map((st) => (hit(g.id, st) ? { ...st, done } : st));
        return { ...t, steps, done: steps.every((st) => st.done) };
      }),
    })));
  }

  // By meal: check one meal's steps of a task (never another meal's).
  async function checkMealSteps(group, task, steps, done) {
    if (steps.some((st) => st.key == null)) { // older cached task: only whole-task check
      const full = tasks.find((t) => t.id === task.task_id);
      if (full) toggle({ ...full, done: !done });
      return;
    }
    const keys = steps.map((st) => st.key);
    markSteps(task.task_id, group.id, keys, done);
    try {
      for (const key of keys) await api.checkPrepItem(task.task_id, { recipe_id: group.id, key, done });
    } catch (e) {
      setErr(e.message);
      load().catch(() => {});
    }
  }

  function chooseView(next) {
    setView(next);
    store.set("prep.view", next);
  }

  async function toggle(task) {
    const done = !task.done;
    patchLocal(task.id, { done });
    markSteps(task.id, null, null, done);
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
      return true;
    } catch (e) {
      patchLocal(task.id, before);
      setErr(e.message);
      return false;
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
        <h1>{Copy.text("tour.how.4.title")}</h1>
        {total > 0 && (
          <button type="button" className="more-btn" aria-label="More options" aria-expanded={menu} onClick={() => setMenu(!menu)}>
            <Icon name="dots" size={24} />
          </button>
        )}
      </header>
      {menu && (
        <div className="action-sheet prep-options">
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

            <div className="pz-view-row">
              <div className="pz-view" role="group" aria-label="Show prep">
                <button type="button" aria-pressed={view === "meal"} onClick={() => chooseView("meal")}>{Copy.text("ui.by.meal")}</button>
                <button type="button" aria-pressed={view === "task"} onClick={() => chooseView("task")}>{Copy.text("ui.by.task")}</button>
              </div>
              {doneCount > 0 && (
                <button type="button" className="pz-done-toggle" onClick={toggleShowDone}>
                  {showDone ? Copy.text("ui.hide.completed") : `Show completed (${doneCount})`}
                </button>
              )}
            </div>

            {view === "meal" && (
              <MealView groups={mealGroups} showDone={showDone} openKey={openMealTask}
                onOpen={(key) => setOpenMealTask(openMealTask === key ? null : key)}
                onCheck={checkMealSteps} />
            )}

            {view === "task" && sections.map((s) => (
              <section key={s.key} id={`prep-${s.key}`} className="pz-section">
                <h2 className="pz-group-label"><span>{s.title}</span><span>{s.done} of {s.all.length}</span></h2>
                {s.shown.length === 0
                  ? <p className="pz-empty">{Copy.text("ui.all.prepped.here")}</p>
                  : s.shown.map((t) => (
                    <PrepRow key={t.id} task={t} open={openId === t.id} reporting={report === t.id}
                      onCheck={() => check(t)}
                      onOpen={() => { setOpenId(openId === t.id ? null : t.id); setReport(null); }}
                      onDone={() => { if (!t.done) toggle(t); openNext(t); }}
                      onSkip={() => openNext(t)}
                      onRate={(next) => { rate(t, next, next < 0 ? t.reason : ""); setReport(next < 0 ? t.id : null); }}
                      onSend={async (reason, note) => {
                        if (await rate(t, -1, reason, note)) setReport(null);
                      }} />
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

function MealView({ groups, showDone, openKey, onOpen, onCheck }) {
  return groups.map((g) => {
    const shown = showDone ? g.tasks : g.tasks.filter((t) => !t.done);
    const left = g.tasks.filter((t) => !t.done).length;
    return (
      <section key={g.id} className="pz-meal">
        <header className="pz-meal-head">
          <a href={`/recipes/${g.id}`} onClick={(e) => { e.preventDefault(); go(`/recipes/${g.id}`); }}>{g.name}</a>
          <span className="pz-meal-meta">{[g.day, left ? `${left} to prep` : "All prepped"].filter(Boolean).join(" · ")}</span>
        </header>
        {shown.map((t) => (
          <MealTaskRow key={t.task_id} group={g} task={t} open={openKey === `${g.id}:${t.task_id}`}
            onOpen={() => onOpen(`${g.id}:${t.task_id}`)} onCheck={onCheck} />
        ))}
      </section>
    );
  });
}

const RING = 2 * Math.PI * 11;

function MealTaskRow({ group, task: t, open, onOpen, onCheck }) {
  const done = t.steps.filter((st) => st.done).length;
  const total = t.steps.length;
  const summary = t.quantities.length ? t.quantities.join(" · ") : total === 1 ? "1 step" : `${total} steps`;
  const progress = done > 0 && !t.done ? `${done} of ${total} · ` : "";
  const id = `pz-meal-${group.id}-${t.task_id}`;
  return (
    <div className={`pz-mtask${open ? " open" : ""}${t.done ? " done" : ""}`}>
      <div className="pz-mtask-head">
        <button type="button" className="pz-ring" onClick={() => onCheck(group, t, t.steps, !t.done)}
          aria-label={`${t.done ? "Mark not done" : Copy.text("ui.mark.done")}: ${t.title} for ${group.name}`}>
          <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
            <circle cx="14" cy="14" r="11" className="pz-ring-track" />
            {done > 0 && !t.done && <circle cx="14" cy="14" r="11" className="pz-ring-fill" strokeDasharray={`${(RING * done) / total} ${RING}`} transform="rotate(-90 14 14)" />}
            {t.done && <path d="M9.2 14.4l3.2 3L18.8 11" className="pz-ring-check" />}
          </svg>
        </button>
        <button type="button" className="pz-toggle" aria-expanded={open} aria-controls={id} onClick={onOpen}>
          <span className="pz-mtask-text">
            <span className="pz-title">{t.title}</span>
            <span className="pz-mtask-summary">{progress}{summary}</span>
          </span>
          <span className="pz-chev" aria-hidden="true"><Icon name="chevron-down" size={14} /></span>
        </button>
      </div>
      {open && (
        <div className="pz-mtask-body" id={id}>
          {t.steps.map((st, i) => (
            <div key={st.key ?? i} className={`pz-mstep${st.done ? " done" : ""}`}>
              {st.key != null ? (
                <button type="button" className="pz-check" aria-label={`${st.done ? "Mark not done" : "Mark done"}: ${st.text}`}
                  onClick={() => onCheck(group, t, [st], !st.done)}>{st.done && <Icon name="check" size={12} />}</button>
              ) : <span className="pz-check pz-check-off" aria-hidden="true" />}
              <p>{st.text}
                {st.quantities.length > 0 && <span className="pz-amount">{st.quantities.join(" · ")}</span>}
                {st.added && <span className="pz-added">{Copy.text("ui.added.by.you")}</span>}</p>
            </div>
          ))}
          {t.storage && <p className="pz-mtask-storage">{t.storage}</p>}
        </div>
      )}
    </div>
  );
}

function PrepRow({ task: t, open, reporting, onCheck, onOpen, onDone, onSkip, onRate, onSend }) {
  const [reason, setReason] = useState(t.reason || "");
  const [note, setNote] = useState(t.reason_note || "");
  const [sending, setSending] = useState(false);
  useEffect(() => {
    if (!reporting) { setReason(t.reason || ""); setNote(t.reason_note || ""); }
  }, [reporting, t.reason, t.reason_note]);
  const amount = (t.quantities || []).filter(Boolean).join(" · ");
  const how = new PrepTaskPresentation(t).instructionGroups;
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
            <p key={i} className="pz-how">{t.meals.length > 1 && <strong>{h.meals.map((m) => m.name).join(", ")}: </strong>}{h.text}
              {h.quantities?.length > 0 && <span className="pz-amount">{h.quantities.join(" · ")}</span>}
              {h.added && <span className="pz-added">{Copy.text("ui.added.by.you")}</span>}</p>
          ))}
          {t.storage && <p className="pz-how">{t.storage}</p>}
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
          </div>
          {reporting && (
            <div className="pz-report">
              <div className="pz-chips" role="group" aria-label="Why not worth prepping ahead?">
                {PREP_REASONS.map(([id, label]) => (
                  <button key={id} type="button" aria-pressed={reason === id} disabled={sending}
                    onClick={() => setReason(reason === id ? "" : id)}>{label}</button>
                ))}
              </div>
              <label htmlFor={`pz-report-${t.id}`}>What's wrong with this step?</label>
              <textarea id={`pz-report-${t.id}`} rows={2} maxLength={500} value={note}
                disabled={sending} placeholder="Wrong amount, unclear step, missing ingredient…" onChange={(e) => setNote(e.target.value)} />
              <button type="button" disabled={sending} onClick={async () => {
                setSending(true);
                try { await onSend(reason, note.trim()); } finally { setSending(false); }
              }}>{sending ? "Sending…" : "Send feedback"}</button>
            </div>
          )}
          {!reporting && t.rating < 0 && (
            <div className="pz-saved-feedback">
              {t.reason && <p>{PREP_REASONS.find(([id]) => id === t.reason)?.[1] || t.reason}</p>}
              {t.reason_note && <p>{t.reason_note}</p>}
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
          <span className="pz-missing-title">{Copy.text("ui.missing.a.prep.step")}</span>
          <span className="muted">{Copy.text("ui.pick.a.step.from.this")}</span>
        </span>
      </button>
      {open && (
        <div className="pz-missing-body">
          <p className="help">{Copy.text("ui.tell.us.a.step.that")}</p>
          {meals == null ? <p className="muted">Loading…</p> : added ? (
            <div className="pz-missing-done" role="status">
              <span className="pz-missing-tick" aria-hidden="true">✓</span>
              <strong>{Copy.text("ui.added.to.your.prep")}</strong>
              <span>{added.text}</span>
              <span className="muted">{added.meal} · marked “Added by you”</span>
              <div className="pz-missing-actions">
                <button type="button" className="btn-secondary" onClick={() => { setAdded(null); pickMeal(null); }}>{Copy.text("ui.add.another")}</button>
                <button type="button" className="btn-primary" onClick={() => { setAdded(null); pickMeal(null); setOpen(false); }}>Done</button>
              </div>
            </div>
          ) : meals.length === 0 ? <p className="muted">{Copy.text("ui.every.step.of.this.weeks")}</p> : (
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
                        <button type="button" className="text-link" disabled={saving} onClick={() => save(meal, st, false)}>{Copy.text("ui.remove.from.prep")}</button>
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
