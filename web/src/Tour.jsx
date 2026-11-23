import { useEffect, useState } from "react";
import { api } from "./api.js";
import { go } from "./nav.js";
import { ALLERGENS, AVOIDS, DIETS, DIET_LABELS, TIMES, cleanDiets, toggleAvoid, toggleDiet } from "./diet.js";
import { Notice } from "./Notice.jsx";
import FoodPhoto from "./FoodPhoto.jsx";
import "./quick-start.css";
import { Copy } from "./Copy.js";

// One line for the notice; Details shows the rest.
const UPDATE_SHORT = "More varied meal plans, cuisine and protein filters, and 58 new recipes.";
// Same words as tour.update in ios/dinnerdesk/copy.json.
const UPDATE =
  "Suggested plans are now less likely to be all one protein or all one kind of dish. Grocery optimizing had been weighted too heavily, causing suggestions to contain all one type of dish (all salmon dishes, all potato dishes etc.) Filters can now choose which cuisines to suggest, and which proteins to offer more or less of. 58 new recipes are in the app.";

// Raise this (and TourView.version on iPhone) with a major update: everyone who saw an older tour
// gets it once more. Households that finished the tour before versions existed count as 1.
export const TOUR_VERSION = 2;

// The tour version this household last finished or skipped; 0 if never.
function tourSeen(prefs = {}) {
  return prefs.tour_version ?? (prefs.tour_done ? 1 : 0);
}

/** After a major update, a one-line notice at the top of the page instead of the tour popup.
 *  Dismiss marks the current tour version seen. */
export function WhatsNew() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    api
      .household()
      .then((hh) => {
        const seen = tourSeen(hh.prefs);
        setShow(seen > 0 && seen < TOUR_VERSION);
      })
      .catch((error) => { throw error; });
  }, []);

  const [err, setErr] = useState("");
  const [details, setDetails] = useState(false);

  // Stays up until the save works; a failed save says so here and Dismiss can be tried again.
  async function dismiss() {
    setErr("");
    try {
      // Only these two: the server merges prefs, and resending pantry_auto_check would reset
      // pantry check-offs on the grocery list.
      await api.putHousehold({ prefs: { tour_done: true, tour_version: TOUR_VERSION } });
      setShow(false);
    } catch (e) {
      setErr(e.message || "Couldn't save. Try again.");
    }
  }

  if (!show) return null;
  return (
    <Notice onDismiss={dismiss}>
      <strong>What’s new:</strong> <span data-tip="tour.update">{details ? UPDATE : UPDATE_SHORT}</span>{" "}
      <button type="button" className="notice-more" aria-expanded={details} onClick={() => setDetails(!details)}>{details ? "Less" : "Details"}</button>
      {err && <span role="alert" className="notice-err"> {err}</span>}
    </Notice>
  );
}

// Quick start: five full screens, one job each, each fitting one phone screen (down to 360×780)
// without scrolling. Same steps and words as TourView.swift and TourView.kt.
const STEPS = ["welcome", "household", "avoid", "week", "ready"];
// Settings shows the first six Dislikes as chips; the tour shows the same six.
const COMMON_AVOIDS = AVOIDS.slice(0, 6);
const MAX_DINNERS = 7;

// Same as avoidLabel in Settings: every word capitalized ("Bell Peppers").
function avoidLabel(id) {
  return id.replace(/\b\w/g, (c) => c.toUpperCase());
}

function Chip({ on, children, onClick }) {
  return (
    <button type="button" className={`qs-chip${on ? " is-on" : ""}`} aria-pressed={on} onClick={onClick}>
      {children}
    </button>
  );
}

function Stepper({ value, min, max, onChange, label, busy }) {
  return (
    <div className="qs-stepper">
      <button type="button" aria-label={`Fewer ${label}`} disabled={busy || value <= min} onClick={() => onChange(value - 1)}>−</button>
      <span aria-live="polite">{value}</span>
      <button type="button" aria-label={`More ${label}`} disabled={busy || value >= max} onClick={() => onChange(value + 1)}>+</button>
    </div>
  );
}

export function Tour() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState("welcome");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  // The household's saved filters, so saving the tour's choices keeps the ones it doesn't show.
  const [saved, setSaved] = useState({});
  const [people, setPeople] = useState(2);
  const [time, setTime] = useState("any");
  const [diets, setDiets] = useState(["omnivore"]);
  const [allergens, setAllergens] = useState([]);
  const [avoids, setAvoids] = useState([]);
  const [dinners, setDinners] = useState(3);
  const [proposal, setProposal] = useState(null);
  const [plan, setPlan] = useState(null);
  const [toBuy, setToBuy] = useState(null);

  function load(hh) {
    const f = hh.prefs?.filters || {};
    setSaved(f);
    if (Array.isArray(f.diets) && f.diets.length) setDiets(cleanDiets(f.diets));
    if (Array.isArray(f.allergens)) setAllergens(f.allergens);
    if (Array.isArray(f.avoids)) setAvoids(f.avoids);
    if (f.time) setTime(f.time);
    const n = Number(hh.prefs?.family_portions);
    if (n >= 1) setPeople(Math.min(12, n));
  }

  useEffect(() => {
    // Replay from Settings skips the welcome screen.
    function start() {
      setErr(""); setProposal(null); setPlan(null); setToBuy(null);
      setStep("household");
      setOpen(true);
      api.household().then(load).catch(() => {});
    }
    window.addEventListener("dinnerdesk-tour", start);
    api
      .household()
      .then((hh) => {
        load(hh);
        // Only a first visit opens the tour; after a major update WhatsNew shows a notice instead.
        if (tourSeen(hh.prefs) === 0) setOpen(true);
      })
      .catch((error) => { throw error; });
    return () => window.removeEventListener("dinnerdesk-tour", start);
  }, []);

  async function act(fn) {
    setBusy(true); setErr("");
    try { await fn(); } catch (e) { setErr(e.message || "Something went wrong. Try again."); }
    finally { setBusy(false); }
  }

  /** Ends the tour; `to` is where to go next, or null to stay on this page. A suggested plan
   *  that wasn't approved stays on Plan for review. */
  async function finish(to = null) {
    setBusy(true);
    try {
      // Send only the tour's own fields; the server merges top-level keys. Writing every pref
      // back re-ticked pantry items on the grocery list (#172).
      await api.putHousehold({ prefs: { tour_done: true, tour_version: TOUR_VERSION } });
    } catch (error) { setBusy(false); throw error; }
    localStorage.setItem("wp_tour_done", "1");
    setBusy(false);
    setOpen(false);
    // Plan may already be on screen (same route), so tell it to load the new plan and filters.
    window.dispatchEvent(new Event("dinnerdesk-plan-changed"));
    if (to) go(to);
  }

  const saveHousehold = () => act(async () => {
    await api.putHousehold({ prefs: { family_portions: people, filters: { ...saved, time } } });
    setSaved({ ...saved, time });
    setStep("avoid");
  });

  // Saves the filters, then asks for a suggested plan that respects them.
  const saveFilters = () => act(async () => {
    const filters = { ...saved, diets, allergens, avoids, time };
    await api.putHousehold({ prefs: { filters } });
    setSaved(filters);
    const caps = await api.suggestionCapabilities();
    if (caps.version < 2 || !caps.review || !caps.resize || !caps.swap) throw new Error(Copy.text("ui.meal.planning.needs.the.updated"));
    const created = await api.createPlan({ meal_count: dinners, keep_current: false });
    setProposal(created);
    setDinners(created.slots?.length || dinners);
    setStep("week");
  });

  const resize = (n) => act(async () => {
    setDinners(n);
    setProposal(await api.resizeSuggestion(proposal.id, n));
  });

  // Swap brings in the next-best match; the server records it as a pass for Taste Lab.
  const swap = (slot) => act(async () => setProposal(await api.swapSuggestion(proposal.id, slot.id)));

  const approve = () => act(async () => {
    const approved = proposal.status === "suggested" ? await api.decideSuggestion(proposal.id, "approve") : proposal;
    setPlan(approved);
    setStep("ready");
    try {
      const g = await api.grocery(approved.id);
      setToBuy((g.lines || []).filter((l) => !l.checked && !l.never_shop).length);
    } catch { setToBuy(null); }
  });

  if (!open) return null;

  const index = STEPS.indexOf(step);
  const back = { avoid: "household", week: "avoid" }[step];

  function Top() {
    return (
      <div className="qs-top">
        {back ? (
          <button type="button" className="qs-back" aria-label="Back" disabled={busy} onClick={() => { setErr(""); setStep(back); }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
          </button>
        ) : <span className="qs-back" aria-hidden="true" />}
        <div className="qs-progress" role="progressbar" aria-valuemin={1} aria-valuemax={STEPS.length} aria-valuenow={index + 1} aria-label={`Step ${index + 1} of ${STEPS.length}`}>
          {STEPS.map((s, i) => <span key={s} className={i <= index ? "is-on" : ""} />)}
        </div>
        {step !== "ready" ? (
          <button type="button" className="text-link qs-skip" disabled={busy} onClick={() => finish(proposal ? "/" : "/recipes")}>Skip</button>
        ) : <span className="qs-skip" />}
      </div>
    );
  }

  const slots = proposal?.slots || [];
  const mealCount = (plan?.slots || slots).length;

  return (
    <div className="qs" role="dialog" aria-modal="true" aria-labelledby="qs-title">
      <div className="qs-screen">
        {step === "welcome" && (
          <>
            <div className="qs-center">
              <span className="qs-pill">{Copy.text("ui.free.no.ads.ever")}</span>
              <h1 id="qs-title" className="qs-hero">{Copy.text("ui.custom.meal.plans.in.5")}</h1>
              <ul className="qs-benefits">
                <li><span className="qs-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6h11M9 12h11M9 18h11" /><path d="M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2" /></svg></span>{Copy.text("ui.grocery.list.built.for.you")}</li>
                <li><span className="qs-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="13" r="8" /><path d="M12 9v4l2.5 2.5M9 2h6" /></svg></span>{Copy.text("ui.prepahead.steps.for.busy.nights")}</li>
                <li><span className="qs-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19c0-8 6-14 15-14-1 9-6 15-14 15" /><path d="M5 19l7-7" /></svg></span>{Copy.text("ui.less.waste.using.your.pantry")}</li>
              </ul>
            </div>
            <button type="button" className="qs-primary" onClick={() => setStep("household")}>{Copy.text("ui.get.started")}</button>
            <div className="qs-links">
              <button type="button" className="text-link" disabled={busy} onClick={() => finish("/recipes")}>{Copy.text("ui.skip.ill.look.around")}</button>
              <a className="text-link" href="/support#ai" target="_blank" rel="noopener">{Copy.text("tour.ai.title")}</a>
            </div>
          </>
        )}

        {step === "household" && (
          <>
            <Top />
            <div className="qs-body">
              <h1 id="qs-title">{Copy.text("ui.whos.eating.dinner")}</h1>
              <p className="qs-sub">{Copy.text("ui.well.size.recipes.and.the")}</p>
              <div className="qs-card qs-people">
                <Stepper value={people} min={1} max={12} label="people" busy={busy} onChange={setPeople} />
                <span>people, most nights</span>
              </div>
              <h2 className="qs-label">{Copy.text("ui.weeknight.cook.time")}</h2>
              <div className="qs-segment" role="radiogroup" aria-label="Weeknight cook time">
                {TIMES.map(([id, label]) => (
                  <button key={id} type="button" role="radio" aria-checked={time === id} className={time === id ? "is-on" : ""} onClick={() => setTime(id)}>
                    {label.replace(" or less", "").replace("Any time", "Any")}
                  </button>
                ))}
              </div>
              <p className="qs-tip">{Copy.text("ui.feeding.a.crowd.one.night")}</p>
            </div>
            {err && <p className="qs-err" role="alert">{err}</p>}
            <button type="button" className="qs-primary" disabled={busy} onClick={saveHousehold}>{busy ? "Saving…" : "Next"}</button>
          </>
        )}

        {step === "avoid" && (
          <>
            <Top />
            <div className="qs-body">
              <h1 id="qs-title">{Copy.text("ui.anything.to.avoid")}</h1>
              <h2 className="qs-label">Diet</h2>
              <p className="qs-note">{Copy.text("ui.only.show.recipes.that.fit")}</p>
              <div className="qs-chips">
                {DIETS.map((d) => <Chip key={d} on={diets.includes(d)} onClick={() => setDiets(toggleDiet(diets, d))}>{DIET_LABELS[d] || d}</Chip>)}
              </div>
              <h2 className="qs-label">Allergies</h2>
              <p className="qs-note">{Copy.text("ui.never.shown.we.check.every")}</p>
              <div className="qs-chips">
                {ALLERGENS.map(([id, text]) => <Chip key={id} on={allergens.includes(id)} onClick={() => setAllergens(toggleAvoid(allergens, id))}>{text}</Chip>)}
              </div>
              <h2 className="qs-label">Dislikes</h2>
              <p className="qs-note">{Copy.text("ui.suggested.less.often.you.can")}</p>
              <div className="qs-chips">
                {COMMON_AVOIDS.map((id) => <Chip key={id} on={avoids.includes(id)} onClick={() => setAvoids(toggleAvoid(avoids, id))}>{avoidLabel(id)}</Chip>)}
              </div>
            </div>
            {err && <p className="qs-err" role="alert">{err}</p>}
            <button type="button" className="qs-primary" disabled={busy} onClick={saveFilters}>{busy ? "Planning your week…" : "Next"}</button>
          </>
        )}

        {step === "week" && (
          <>
            <Top />
            <div className="qs-body">
              <h1 id="qs-title">{Copy.text("ui.heres.your.week")}</h1>
              <p className="qs-sub">{Copy.text("ui.picked.for.you.swap.anything")}</p>
              <div className="qs-card qs-count">
                <span>{Copy.text("ui.dinners.this.week")}</span>
                <Stepper value={dinners} min={1} max={MAX_DINNERS} label="dinners" busy={busy} onChange={resize} />
              </div>
              <ul className="qs-meals">
                {slots.map((s) => (
                  <li key={s.id}>
                    <FoodPhoto path={s.photo_path} />
                    <div>
                      <strong>{s.recipe_name}</strong>
                      {s.cooking_minutes ? <span>{s.cooking_minutes} min</span> : null}
                    </div>
                    {proposal.suggested_recipe_ids?.includes(s.recipe_id) && (
                      <button type="button" className="qs-swap" disabled={busy} aria-label={`Swap ${s.recipe_name}`} onClick={() => swap(s)}>
                        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h13l-3-3M20 17H7l3 3" /></svg>Swap
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
            {err && <p className="qs-err" role="alert">{err}</p>}
            <button type="button" className="qs-primary" disabled={busy || !slots.length} onClick={approve}>{Copy.text("ui.looks.good")}</button>
          </>
        )}

        {step === "ready" && (
          <>
            <Top />
            <div className="qs-body">
              <h1 id="qs-title">{Copy.text("ui.your.week.is.ready")}</h1>
              <p className="qs-sub">
                {mealCount} dinner{mealCount === 1 ? "" : "s"} for {people}
                {toBuy != null ? ` · ${toBuy} thing${toBuy === 1 ? "" : "s"} to buy` : ""}
              </p>
              <ol className="qs-tips">
                <li><span>1</span><p><strong>Plan</strong> {Copy.text("ui.give.meals.a.day.when")}</p></li>
                <li><span>2</span><p><strong>Grocery</strong> {Copy.text("ui.your.list.builds.itself.check")}</p></li>
                <li><span>3</span><p><strong>{Copy.text("ui.prep.ahead")}</strong> {Copy.text("ui.got.time.on.the.weekend")}</p></li>
              </ol>
              <p className="qs-lab">
                Want better picks next week?{" "}
                <button type="button" className="text-link" disabled={busy} onClick={() => finish("/settings/tastelab?swipe=1")}>Try Taste Lab</button>
                {" "}(about 2 min)
              </p>
            </div>
            {err && <p className="qs-err" role="alert">{err}</p>}
            <button type="button" className="qs-primary" disabled={busy} onClick={() => finish("/")}>Done</button>
          </>
        )}
      </div>
    </div>
  );
}
