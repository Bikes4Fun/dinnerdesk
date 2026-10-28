import { useEffect, useState } from "react";
import { api } from "./api.js";
import { go } from "./nav.js";
import { AVOIDS, DIETS, cleanDiets, toggleAvoid, toggleDiet } from "./diet.js";
import { TourPicture } from "./TourPicture.jsx";
import { Sparkle, Tip } from "./Tip.jsx";
// Real iPhone screenshots for how-to cards, by card index; the others use TourPicture.
import suggestionsShot from "./images/tour-suggestions.jpg";
import scheduleShot from "./images/tour-schedule.jpg";
import draftShot from "./images/tour-draft.jpg";
import storesShot from "./images/tour-stores.jpg";

const SHOTS = { 0: suggestionsShot, 1: scheduleShot, 2: draftShot, 3: storesShot };
// The drawn picture for each remaining card (TourPicture: 2 checked-off list, 3 prep).
const DRAWINGS = { 4: 2, 5: 3 };
// The tips & Apple Watch card shows a real tip instead of a picture.
const TIPS_CARD = 6;

const TIMES = [
  ["any", "Any time"],
  ["20", "≤20 min"],
  ["30", "≤30 min"],
  ["45", "≤45 min"],
];
const HOW = [
  {
    title: "Fewer dinner decisions",
    body: "Start with four meal suggestions matched to your household’s tastes and dietary needs. Approve the plan or swap a meal, and your choices help improve future suggestions. No browsing required. If you have something in mind, pick it yourself and let us suggest the rest.",
  },
  {
    title: "This plan",
    body: "Tap the calendar to schedule meals for a specific day. Tap Edit to change servings, remove a meal or provide feedback.",
  },
  {
    title: "Plan ahead",
    body: "Start next week’s plan without losing this one. Tap ••• next to This week, then Save as draft. Your current plan stays until you’re ready. The same menu switches to Grid View.",
  },
  {
    title: "Grocery",
    body: "Built from this plan. Tap a store at the top to shop one store at a time. Set your stores in the Grocery menu › Edit stores.",
  },
  {
    title: "Pantry",
    body: "Add what you have in My kitchen › Pantry and choose whether it starts checked off. Staples like salt go in Always checked off.",
  },
  {
    title: "Weekend prep",
    body: "Prep your own meal kit, without the price or carbon footprint of a meal kit service. When you have spare time, measure, chop and make sauces ahead. On weeknights everything is ready in the right amounts. Just cook. Make-ahead steps from your plan show up here.",
  },
  {
    title: "Tips & Apple Watch",
    body: "Purple cards with a sparkle explain a feature right where you use it. On Apple Watch, see this plan and your grocery list on your wrist, and tap to check off groceries or mark a meal cooked.",
  },
  {
    title: "Taste Lab",
    body: "Swipe meals you’d cook or pass on. Your likes shape future suggestions, and a pass isn’t suggested again. Find it under More.",
  },
];

// Same words as tour.ai.* in ios/dinnerdesk/copy.json.
const AI = [
  ["Recipe photos are made with AI", "Recipes are not. They come from reliable sources."],
  ["We never copy photos", "Recipes can’t be copyrighted, but photos can."],
  ["Made on our own computer", "Our AI runs on a machine we own, not in a data center."],
  ["Real photos are coming", "We’ll replace AI photos as we cook, and you’ll be able to share yours."],
];

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

  async function dismiss() {
    setShow(false);
    const hh = await api.household();
    await api.putHousehold({ prefs: { ...(hh.prefs || {}), tour_done: true, tour_version: TOUR_VERSION } });
  }

  if (!show) return null;
  return (
    <div className="guest-notice" data-tip="tour.update">
      What’s new: {UPDATE} <button type="button" onClick={dismiss}>Dismiss</button>
    </div>
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

  async function finish(saveFilters, stay) {
    setBusy(true);
    try {
      const hh = await api.household();
      const prefs = { ...(hh.prefs || {}), tour_done: true, tour_version: TOUR_VERSION };
      if (saveFilters) prefs.filters = { diets, avoids, time };
      await api.putHousehold({ prefs });
    } catch (error) { setBusy(false); throw error; }
    localStorage.setItem("wp_tour_done", "1");
    setBusy(false);
    setOpen(false);
    if (!stay) go("/recipes");
  }

  async function pickTasteLab() {
    await finish(false, true);
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
              <button type="button" className="text-link" disabled={busy} onClick={() => finish(false, true)}>
                Skip
              </button>
            </div>
          </>
        )}
        {step === "eat" && (
          <>
            <h2 id="tour-title">What to eat</h2>
            <p className="help" data-tip="tour.filters">Tap what fits. Change this later in Settings → Filters.</p>
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
            <button type="button" className="btn-primary block" disabled={busy} onClick={() => finish(true)}>
              {busy ? "Saving…" : "Start browsing"}
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
            <button type="button" className="btn-primary block" onClick={() => setStep("how")}>
              How to use
            </button>
            <button type="button" className="text-link tour-skip" disabled={busy} onClick={() => finish(false)}>
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
              <button type="button" className="btn-primary block" onClick={() => setHow(how + 1)}>
                Next
              </button>
            ) : (
              <button type="button" className="btn-primary block" onClick={() => setStep("prefs")}>
                Next
              </button>
            )}
            <button type="button" className="text-link tour-skip" disabled={busy} onClick={() => finish(false)}>
              Skip rest
            </button>
          </>
        )}
        {step === "prefs" && (
          <>
            {/* Same words as tour.prefs.* in ios/dinnerdesk/copy.json. */}
            <h2 id="tour-title">Make it yours</h2>
            <p className="help" data-tip="tour.prefs">
              Tell us what your household eats and what to avoid, and we’ll start suggesting meal plans made for you.
            </p>
            <button type="button" className="btn-primary block" onClick={() => setStep("eat")}>
              Next
            </button>
          </>
        )}
      </div>
    </div>
  );
}
