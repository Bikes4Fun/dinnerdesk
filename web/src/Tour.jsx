import { useEffect, useState } from "react";
import { api } from "./api.js";
import { go } from "./nav.js";
import { AVOIDS, DIETS, cleanDiets, toggleAvoid, toggleDiet } from "./diet.js";
import { TourPicture } from "./TourPicture.jsx";
import { Sparkle, Tip } from "./Tip.jsx";
import { Notice } from "./Notice.jsx";
// Real iPhone screenshots for how-to cards, by card index; the others use TourPicture.
import suggestionsShot from "./images/tour-suggestions.jpg";
import storesShot from "./images/tour-stores.jpg";

// Order chosen on #24: Suggestions, Review and approve, Grocery, Weekend prep, Recipes and tips,
// Taste Lab. Same order and pictures as TourView.swift and TourView.kt.
const SHOTS = { 0: suggestionsShot, 2: storesShot };
// Drawn pictures (TourPicture: 0 suggestions, 3 prep).
const DRAWINGS = { 1: 0, 3: 3 };
// The recipes and tips card shows a real tip instead of a picture.
const TIPS_CARD = 4;

const TIMES = [
  ["any", "Any time"],
  ["20", "≤20 min"],
  ["30", "≤30 min"],
  ["45", "≤45 min"],
];
// Same words as tour.how.* in ios/dinnerdesk/copy.json.
const HOW = [
  { title: "Suggestions", body: "Get four dinners matched to your household’s tastes and diet. No browsing needed." },
  { title: "Review and approve", body: "Swap any meal you don’t want, then approve. Your current plan stays until you do." },
  { title: "Grocery", body: "Your list is built from the plan, with amounts combined. Pantry items can start checked off. Tap a store at the top to shop one store at a time." },
  { title: "Weekend prep", body: "When you have time, chop, measure and make sauces ahead. On weeknights, just cook." },
  { title: "Recipes and tips", body: "Browse recipes or add your own. Purple cards with a ★ explain a feature right where you use it." },
  { title: "Taste Lab", body: "Swipe meals you’d cook or pass on to sharpen your suggestions. Find it anytime under More." },
];

// Same words as tour.ai.* in ios/dinnerdesk/copy.json.
const AI = [
  ["Are these recipes AI-generated?", "No. These are real recipes developed by people and shared publicly by reliable sources."],
  ["AI photos and wording", "We use AI to create representative photos and rewrite descriptions and instructions, rather than copy the source’s photos or exact wording. The photos are inspiration, not the exact result."],
  ["Made on our own computer", "Our AI runs on a machine we own, not in a data center."],
  ["Reviewed by our team", "Our team reviews the AI-generated photos and wording. We’re working through cooking the recipes, checking ingredients and steps, and replacing AI images with our own photos."],
];

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

export function Tour() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState("welcome");
  const [how, setHow] = useState(0);
  const [diets, setDiets] = useState(["omnivore"]);
  const [avoids, setAvoids] = useState([]);
  const [time, setTime] = useState("any");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    function start() {
      setStep("welcome");
      setHow(0);
      setOpen(true);
    }
    window.addEventListener("dinnerdesk-tour", start);
    api
      .household()
      .then((hh) => {
        const f = hh.prefs?.filters || {};
        if (Array.isArray(f.diets) && f.diets.length) setDiets(cleanDiets(f.diets));
        if (Array.isArray(f.avoids)) setAvoids(f.avoids);
        if (f.time) setTime(f.time);
        // Only a first visit opens the tour; after a major update WhatsNew shows a notice instead.
        if (tourSeen(hh.prefs) === 0) setOpen(true);
      })
      .catch((error) => { throw error; });
    return () => window.removeEventListener("dinnerdesk-tour", start);
  }, []);

  /** Ends the tour; `to` is where to go next, or null to stay on this page. */
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
    if (to) go(to);
  }

  // Filters come before the how-to cards (#24), so they're saved on Next: skipping later keeps them.
  async function saveFilters() {
    setBusy(true);
    try {
      await api.putHousehold({ prefs: { filters: { diets, avoids, time } } });
    } finally { setBusy(false); }
    setStep("how");
  }

  async function pickTasteLab() {
    await finish();
    go("/settings/tastelab");
  }

  if (!open) return null;

  const howStep = HOW[how];

  return (
    <div className="tour-scrim" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      <div className="tour-card">
        {step === "welcome" && (
          <>
            <h2 id="tour-title">Welcome to Dinnerdesk</h2>
            <p className="help" data-tip="tour.welcome">
              Quick start walks through eat and how. Taste Lab is the swipe kitchen. Skip anytime.
            </p>
            <div className="tour-actions">
              <button type="button" className="btn-primary" onClick={() => setStep("ai")}>
                Quick start
              </button>
              <button type="button" className="btn-secondary" disabled={busy} onClick={pickTasteLab}>
                Taste Lab
              </button>
              <button type="button" className="text-link" disabled={busy} onClick={() => finish()}>
                Skip
              </button>
            </div>
          </>
        )}
        {step === "eat" && (
          <>
            {/* Same words as tour.filters.* in ios/dinnerdesk/copy.json. */}
            <h2 id="tour-title">What do you eat?</h2>
            <p className="help" data-tip="tour.filters">Tap what fits, and suggestions are made for your household. Change this anytime in Settings → Filters.</p>
            <h3 className="block-label">Diet</h3>
            <div className="chip-row wrap filter-chips">
              {DIETS.map((d) => (
                <button
                  key={d}
                  type="button"
                  className={`chip${diets.includes(d) ? " is-on" : ""}`}
                  onClick={() => setDiets(toggleDiet(diets, d))}
                >
                  {d}
                </button>
              ))}
            </div>
            <h3 className="block-label">Avoid</h3>
            <div className="chip-row wrap filter-chips">
              <button type="button" className={`chip${avoids.length ? "" : " is-on"}`} onClick={() => setAvoids([])}>
                none
              </button>
              {AVOIDS.map((d) => (
                <button
                  key={d}
                  type="button"
                  className={`chip${avoids.includes(d) ? " is-on" : ""}`}
                  onClick={() => setAvoids(toggleAvoid(avoids, d))}
                >
                  {d}
                </button>
              ))}
            </div>
            <h3 className="block-label">Cook time</h3>
            <div className="chip-row wrap filter-chips">
              {TIMES.map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={`chip${time === id ? " is-on" : ""}`}
                  onClick={() => setTime(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <button type="button" className="btn-primary block" disabled={busy} onClick={saveFilters}>
              {busy ? "Saving…" : "Next"}
            </button>
            <button type="button" className="text-link tour-skip" disabled={busy} onClick={() => finish("/recipes")}>
              Skip the tour
            </button>
          </>
        )}
        {step === "ai" && (
          <>
            <h2 id="tour-title">How we use AI</h2>
            <ul className="tour-points">
              {AI.map(([title, body], i) => (
                <li key={title} data-tip={`tour.ai.${i + 1}`}>
                  <strong>{title}</strong>
                  <span>{body}</span>
                </li>
              ))}
            </ul>
            <p className="tour-more">
              <a className="text-link" href="/support#ai" target="_blank" rel="noopener">More about how we use AI</a>
            </p>
            <button type="button" className="btn-primary block" onClick={() => setStep("eat")}>
              Next
            </button>
            <button type="button" className="text-link tour-skip" disabled={busy} onClick={() => finish("/recipes")}>
              Skip the tour
            </button>
          </>
        )}
        {step === "how" && howStep && (
          <>
            <p className="tour-kicker">
              How to use · {how + 1} of {HOW.length}
            </p>
            <h2 id="tour-title">{howStep.title}</h2>
            <p className="help tour-how-text" data-tip={`tour.how.${how + 1}`}>{howStep.body}</p>
            {SHOTS[how] ? (
              <>
                {how === 0 && (
                  <p className="tour-tap">
                    On Plan, tap <span className="tour-fake-btn"><Sparkle /> New meal plan</span>
                  </p>
                )}
                <img className="tour-shot" src={SHOTS[how]} alt="" />
              </>
            ) : DRAWINGS[how] !== undefined ? (
              <TourPicture index={DRAWINGS[how]} />
            ) : how === TIPS_CARD ? (
              <Tip id="recipes.ai-photo">This photo was made with AI. It shows the kind of dish, not this exact recipe.</Tip>
            ) : null}
            {how + 1 < HOW.length ? (
              <>
                <button type="button" className="btn-primary block" onClick={() => setHow(how + 1)}>
                  Next
                </button>
                <button type="button" className="text-link tour-skip" disabled={busy} onClick={() => finish("/recipes")}>
                  Skip rest
                </button>
              </>
            ) : (
              // Last card (Taste Lab): start planning, or try Taste Lab now.
              <>
                <button type="button" className="btn-primary block" disabled={busy} onClick={() => finish("/")}>
                  {busy ? "Saving…" : "Start planning"}
                </button>
                <button type="button" className="btn-secondary block" disabled={busy} onClick={pickTasteLab}>
                  Try Taste Lab
                </button>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
