import { useEffect, useState } from "react";
import { api, photoSrc } from "../api.js";
import { Icon } from "../icons.jsx";
import { Thumbs } from "../Thumbs.jsx";
import { go } from "../nav.js";
import { useWeek } from "../week.jsx";

const shortDay = (d) => d.toLocaleDateString(undefined, { month: "short", day: "numeric" });

const inHistory = (p) => (p.status !== "draft" && p.status !== "active") || Boolean(p.decision);

/** The plan's own name, or the week it starts when it's still called "This week". */
function planHeading(p) {
  const title = (p.title || "").trim();
  if (title && title !== "This week") return title;
  return `Week of ${shortDay(new Date(`${p.start_date}T12:00:00`))}`;
}

function planStatus(p) {
  if (p.decision === "approve") return "Approved";
  if (p.decision === "decline") return "Declined";
  return { draft: null, active: "Current plan", suggested: "Waiting for review" }[p.status] ?? (p.status ? p.status[0].toUpperCase() + p.status.slice(1) : null);
}

/** One saved plan: name, dates, meal count and status, the first meals, and when it was saved. */
function SavedPlanSummary({ plan: p }) {
  const start = new Date(`${p.start_date}T12:00:00`);
  const end = new Date(start);
  end.setDate(end.getDate() + Math.max(p.days || 1, 1) - 1);
  const names = p.slots.map((s) => s.recipe_name);
  const meals = names.slice(0, 3).join(", ") + (names.length > 3 ? ` +${names.length - 3} more` : "");
  const saved = p.created_at ? new Date(p.created_at) : null;
  return <span className="saved-summary">
    <strong>{planHeading(p)}</strong>
    <span>{[`${shortDay(start)} – ${shortDay(end)}`, `${names.length} ${names.length === 1 ? "meal" : "meals"}`, planStatus(p)].filter(Boolean).join(" · ")}</span>
    {meals && <span className="muted">{meals}</span>}
    {saved && !Number.isNaN(saved.getTime()) && <span className="muted">Saved {saved.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span>}
  </span>;
}

function slotDate(plan, index) {
  const date = new Date(`${plan.start_date}T12:00:00`);
  date.setDate(date.getDate() + index);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
function dayLabel(plan, index) {
  return new Date(`${slotDate(plan, index)}T12:00:00`).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });
}

export function Plan() {
  const week = useWeek();
  const [swapping, setSwapping] = useState(null);
  const [swapQuery, setSwapQuery] = useState("");
  const [swapOptions, setSwapOptions] = useState([]);
  const [swapError, setSwapError] = useState("");
  const [swapLoading, setSwapLoading] = useState(false);
  const [proposal, setProposal] = useState(null);
  const [keepCurrent, setKeepCurrent] = useState(false);
  const [plan, setPlan] = useState(null);
  const [editing, setEditing] = useState(false);
  const [grid, setGrid] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [placing, setPlacing] = useState(null);
  const [date, setDate] = useState("");
  const [saved, setSaved] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [making, setMaking] = useState(null);
  const [suggested, setSuggested] = useState(false);

  useEffect(() => {
    if (!swapping || !proposal) return;
    let active = true;
    setSwapLoading(true);
    const timer = setTimeout(() => api.swapOptions(proposal.id, swapping.id, swapQuery)
      .then((box) => { if (active) { setSwapOptions(box.recipes); setSwapError(""); } })
      .catch((e) => { if (active) setSwapError(e.message); })
      .finally(() => { if (active) setSwapLoading(false); }), 250);
    return () => { active = false; clearTimeout(timer); };
  }, [swapping, proposal?.id, swapQuery]);
  async function load() { setPlan(await api.plan()); setProposal((await api.pendingSuggestion()).plan); await week.load(); }
  useEffect(() => { load().catch((e) => setErr(e.message)); }, []);
  async function act(work) {
    setBusy(true); setErr(""); setMessage("");
    try { await work(); } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }
  // Thumbs on a meal: 👎 = never suggested again, 👍 = more like it.
  async function rate(slot, rating) {
    const setRating = (r) => setPlan((p) => ({ ...p, slots: p.slots.map((s) => s.recipe_id === slot.recipe_id ? { ...s, rating: r } : s) }));
    const before = slot.rating || 0;
    setRating(rating);
    try { await api.rateMeal(slot.recipe_id, rating); } catch (e) { setRating(before); setErr(e.message); }
  }
  async function patch(slot, body) {
    const updated = await api.patchSlot(slot.id, body);
    setPlan((p) => ({ ...p, slots: p.slots.map((s) => s.id === slot.id ? updated : s) }));
    await week.load();
  }
  async function markCooked(ids) {
    for (const slot of plan.slots.filter((s) => ids.has(s.id) && !s.cooked)) await patch(slot, { cooked: true });
    setSelected(new Set());
  }
  async function removeSelected() {
    for (const slot of plan.slots.filter((s) => selected.has(s.id))) setPlan(await api.deleteSlot(slot.id));
    setSelected(new Set()); await week.load();
  }
  async function newPlan(source, mealCount) {
    const body = {};
    if (source != null) body.source_plan_id = source;
    if (mealCount) { const caps = await api.suggestionCapabilities(); if (caps.version < 2 || !caps.review || !caps.resize || !caps.swap) throw new Error("Meal planning needs the updated server. Please try again after the server update."); body.meal_count = mealCount; body.keep_current = keepCurrent; }
    const created = await api.createPlan(body);
    if (created.status === "suggested") setProposal(created);
    else setPlan(created);
    setSuggested(Boolean(created.suggestion_note));
    if (created.suggestion_note) setMessage(created.suggestion_note);
    setSaved(null); setSelected(new Set()); setPlacing(null); setMaking(null); await week.load();
  }
  function toggleSelection(id) {
    setSelected((current) => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next; });
  }
  function deleteSaved(p) {
    if (window.confirm(`Delete ${planHeading(p)}?`)) act(async () => { await api.deletePlan(p.id); setSaved(saved.filter((other) => other.id !== p.id)); });
  }

  function schedule(slot) {
    setPlacing(slot);
    const today = new Date();
    const localToday = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    setDate(slot.day_index == null ? localToday : slotDate(plan, slot.day_index));
  }

  if (!plan) return <section className="screen pad">{err || "Loading…"}</section>;
  const groups = [...new Set(plan.slots.map((s) => s.day_index ?? -1))].sort((a, b) => a - b);
  const today = new Date();
  const earliest = [plan.start_date, `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`].sort().at(-1);

  return <section className="screen">
    <header className="top">
      <h1>{plan.title}</h1>
      <div className="top-actions">
        <button type="button" className="text-link" onClick={() => { setEditing(!editing); setSelected(new Set()); }}>{editing ? "Done" : "Edit"}</button>
        <details className="plan-menu">
          <summary aria-label="Plan menu">⋯</summary>
          <div>
            <button type="button" onClick={() => { setEditing(!editing); setSelected(new Set()); }}> {editing ? "Finish editing" : "Edit this plan"}</button>
            <button type="button" disabled={busy} onClick={() => act(() => markCooked(new Set(plan.slots.map((s) => s.id))))}>Mark all cooked</button>
            <button type="button" onClick={() => setGrid(!grid)}>{grid ? "List" : "Grid"} View</button>
            <button type="button" disabled={busy} onClick={() => {
              const title = window.prompt("Draft name", plan.title);
              if (title?.trim()) act(async () => { await api.createPlan({ title: title.trim(), draft: true, source_plan_id: plan.id }); setMessage("Plan saved as draft."); });
            }}>Save as draft</button>
            <button type="button" disabled={busy} onClick={() => act(async () => setSaved((await api.plans()).plans))}>View drafts</button>
            <button type="button" disabled={busy} onClick={(e) => { e.currentTarget.closest("details")?.removeAttribute("open"); act(() => newPlan(undefined, 4)); }}>New meal plan</button>
            <button type="button" disabled={busy} onClick={() => setMaking("how")}>Choose my own meals</button>
          </div>
        </details>
      </div>
    </header>
    <div className="scroll pad">
      {err && <p role="alert" className="banner err">{err}</p>}
      {message && <p role="status">{message}</p>}
      {proposal && <section className="saved-plans">
        <h2>Review your suggestions</h2>
        <label>Meals <select value={proposal.slots.length} disabled={busy} onChange={(e) => act(async () => setProposal(await api.resizeSuggestion(proposal.id, Number(e.target.value))))}>
          {Array.from({ length: 14 }, (_, i) => i + 1).filter((n) => n >= proposal.slots.length - proposal.suggested_recipe_ids.length).map((n) => <option key={n} value={n}>{n}</option>)}
        </select></label>
        <p>Your plan and groceries stay in place until you approve.</p>
        <button type="button" className="text-link" onClick={() => go("/settings/tastelab?swipe=1")}>Improve suggestions</button>
        <div className="plan-meal-grid">
        {proposal.slots.map((s) => <div key={s.id} className="plan-meal grid">
          {s.photo_path && <img src={photoSrc(s.photo_path)} alt="" style={{ width: "100%", aspectRatio: "1", objectFit: "cover", borderRadius: 12 }} />}
          <div><strong>{s.recipe_name}</strong><br />
            {proposal.suggested_recipe_ids?.includes(s.recipe_id) ? <button disabled={busy} onClick={() => { setSwapping(s); setSwapQuery(""); setSwapOptions([]); }}>Swap meal</button> : <span>Your selection</span>}
          </div>
        </div>)}
        </div>
        <button disabled={busy} onClick={() => act(async () => { setPlan(await api.decideSuggestion(proposal.id, "approve")); setProposal(null); await week.load(); })}>Approve plan</button>
        <button disabled={busy} onClick={() => act(async () => { await api.decideSuggestion(proposal.id, "decline"); setProposal(null); await newPlan(null, Math.max(1, proposal.suggested_recipe_ids.length)); })}>Decline and suggest another plan</button>
      </section>}
      {suggested && <p><button type="button" className="text-link" onClick={() => go("/settings/tastelab?swipe=1")}>Improve your results</button></p>}
      {saved && <section className="saved-plans">
        <h2>Drafts</h2>
        {!saved.some((p) => p.status === "draft") && <p className="muted">No drafts yet. Use ⋯ → Save as draft to keep a plan for later.</p>}
        {saved.filter((p) => p.status === "draft").map((p) => <div key={p.id} className="saved-row">
          <button type="button" className="saved-row-main" disabled={busy} onClick={() => act(() => newPlan(p.id))}><SavedPlanSummary plan={p} /></button>
          <button type="button" className="saved-row-delete" disabled={busy} aria-label={`Delete ${planHeading(p)}`} onClick={() => deleteSaved(p)}><Icon name="trash" size={18} /></button>
        </div>)}
        <h2>Plan history</h2>
        {!saved.some(inHistory) && <p className="muted">No past plans yet. Plans you approve or finish show up here.</p>}
        {saved.filter(inHistory).map((p) => <div key={p.id} className="saved-row">
          <details className="saved-row-main"><summary><SavedPlanSummary plan={p} /></summary><ul>{p.slots.map((s) => <li key={s.id}><button className="text-link" onClick={() => go(`/recipes/${s.recipe_id}`)}>{s.recipe_name}</button> · {s.servings} servings · {s.cooked ? "Cooked" : "Not cooked"}</li>)}</ul></details>
          {p.status !== "active" && <button type="button" className="saved-row-delete" disabled={busy} aria-label={`Delete ${planHeading(p)}`} onClick={() => deleteSaved(p)}><Icon name="trash" size={18} /></button>}
        </div>)}
        <button type="button" className="text-link" onClick={() => setSaved(null)}>Close saved plans</button>
      </section>}
      {editing && plan.slots.length > 0 && <div className="plan-bulk">
        <button type="button" onClick={() => setSelected(selected.size === plan.slots.length ? new Set() : new Set(plan.slots.map((s) => s.id)))}>{selected.size === plan.slots.length ? "Deselect all" : "Select all"}</button>
        <span>{selected.size} selected</span>
        <button type="button" disabled={busy || !selected.size} onClick={() => act(() => markCooked(selected))}>Mark cooked</button>
        <button type="button" disabled={busy || !selected.size} onClick={() => { if (window.confirm(`Remove ${selected.size} meals?`)) act(removeSelected); }}>Remove</button>
      </div>}
      {!plan.slots.length && <p className="help" data-tip="plan.empty">Nothing selected yet. Add meals from Recipes.</p>}
      {groups.map((day) => <section key={day}>
        {day >= 0 && <h2 className="block">{dayLabel(plan, day)}</h2>}
        <div className={grid ? "plan-meal-grid" : "plan-meal-list"}>
          {plan.slots.filter((s) => (s.day_index ?? -1) === day).sort((a, b) => Number(a.cooked) - Number(b.cooked) || a.id - b.id).map((slot) => <article key={slot.id} className={`plan-meal${grid ? " grid" : ""}${editing ? " editing" : ""}`}>
            {editing && <label className="meal-select"><input aria-label={`Select ${slot.recipe_name}`} type="checkbox" checked={selected.has(slot.id)} onChange={() => toggleSelection(slot.id)} /></label>}
            <div className={`meal-photo-wrap${slot.cooked ? " plan-completed" : ""}`}>
              <button type="button" className="meal-photo-btn" aria-label={`Open ${slot.recipe_name}`} onClick={() => go(`/recipes/${slot.recipe_id}`)}>
                {slot.photo_path ? <img src={photoSrc(slot.photo_path)} alt="" /> : <span className="ph" />}
              </button>
              {!editing && <button type="button" className="meal-check" disabled={busy} aria-pressed={slot.cooked} aria-label={slot.cooked ? "Mark not cooked" : "Mark cooked"} onClick={() => act(() => patch(slot, { cooked: !slot.cooked }))}>{slot.cooked ? "✓" : ""}</button>}
            </div>
            <div className="meal-copy">
              <button type="button" className={`meal-title${slot.cooked ? " plan-completed" : ""}`} onClick={() => go(`/recipes/${slot.recipe_id}`)}><strong>{slot.recipe_name}</strong></button>
              {!editing && <span className="muted">{slot.servings} servings</span>}
        
              {editing && <>
                <div className="meal-edit-controls">
                  <button type="button" className="meal-schedule" aria-label={`Schedule ${slot.recipe_name}`} onClick={() => schedule(slot)}><Icon name="calendar" size={16} /> {slot.day_index == null ? "Schedule" : new Date(`${slotDate(plan, slot.day_index)}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                  </button>
                  <div className="meal-servings">
                    <button type="button" disabled={busy || slot.servings <= 1} onClick={() => act(() => patch(slot, { servings: slot.servings - 1 }))}>
                      <Icon name="minus" size={16} />
                    </button>
                    <span>{slot.servings} servings</span>
                    <button type="button" disabled={busy || slot.servings >= 50} onClick={() => act(() => patch(slot, { servings: slot.servings + 1 }))}>
                      <Icon name="plus" size={16} />
                    </button>
                  </div>
                </div>
                <span className="meal-thumbs">
                  <Thumbs rating={slot.rating || 0} subject={slot.recipe_name} onRate={(r) => rate(slot, r)} />
                  {slot.rating < 0 && <span className="muted">Won’t be suggested again</span>}
                  {slot.rating > 0 && <span className="muted">We’ll suggest more like this</span>}
                </span>
              </>}
            </div>
          </article>)}
        </div>
      </section>)}
      <button type="button" className="ghost-add" onClick={() => go("/recipes")}>+ Add meals</button>
    </div>
    {swapping && <div className="sheet-backdrop"><section className="schedule-sheet" style={{maxHeight: "calc(100dvh - 32px)", overflowY: "auto"}} role="dialog" aria-modal="true" aria-labelledby="swap-title">
      <h2 id="swap-title">Choose a replacement</h2>
      <p>Replace {swapping.recipe_name}</p>
      <input style={{width: "100%", boxSizing: "border-box"}} aria-label="Search replacement meals" placeholder="Search meals or ingredients" value={swapQuery} onChange={(e) => setSwapQuery(e.target.value)} />
      {swapError && <p role="alert">{swapError}</p>}
      {swapLoading ? <p>Loading…</p> : swapOptions.length === 0 ? <p>No matching meals. Try another search or loosen Settings → Filters.</p> : swapOptions.map((option) => <button key={option.id} className="list-link" disabled={busy} onClick={() => act(async () => { setProposal(await api.swapSuggestion(proposal.id, swapping.id, option.id)); setSwapping(null); })}>{option.name}{option.cooking_minutes ? ` · ${option.cooking_minutes} min` : ""}</button>)}
      <button onClick={() => setSwapping(null)}>Cancel</button>
    </section></div>}
    {making && <div className="sheet-backdrop" role="presentation"><section className="schedule-sheet" role="dialog" aria-modal="true" aria-labelledby="new-plan-title">
      {making === "how" && <>
        <h2 id="new-plan-title">New meal plan</h2>
        <p>Choose your own meals or start with four suggestions.</p>
        {!!plan.slots.length && <label><input type="checkbox" checked={keepCurrent} onChange={(e) => setKeepCurrent(e.target.checked)} />Keep my selected meals</label>}
        <button type="button" className="btn-secondary block" disabled={busy} onClick={() => act(() => newPlan())}>I'll choose the meals</button>
        <button type="button" className="btn-primary block" disabled={busy} onClick={() => act(() => newPlan(undefined, 4))}>Suggest 4 meals</button>
        <button type="button" onClick={() => setMaking(null)}>Cancel</button>
      </>}
    </section></div>}
    {placing && <div className="sheet-backdrop" role="presentation"><section className="schedule-sheet" role="dialog" aria-modal="true" aria-labelledby="schedule-title">
      <h2 id="schedule-title">Schedule {placing.recipe_name}</h2>
      <label>Meal date <input type="date" value={date} min={earliest} onChange={(e) => setDate(e.target.value)} /></label>
      <button type="button" className="btn-primary block" disabled={busy || !date || date < earliest} onClick={() => act(async () => { await patch(placing, { scheduled_date: date }); setPlacing(null); })}>Save date</button>
      <button type="button" disabled={busy} onClick={() => act(async () => { await patch(placing, { unschedule: true }); setPlacing(null); })}>Unschedule</button>
      <button type="button" onClick={() => setPlacing(null)}>Cancel</button>
    </section></div>}
  </section>;
}
