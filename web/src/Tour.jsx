import { useEffect, useState } from "react";
import { api } from "./api.js";
import { go } from "./nav.js";
import { AVOIDS, DIETS, cleanDiets, toggleAvoid, toggleDiet } from "./diet.js";
import { TourPicture } from "./TourPicture.jsx";

const TIMES = [
  ["any", "Any time"],
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
    body: "New meals are added without a day. Give them a day when you’re ready. Tap Edit to change servings or remove a meal.",
  },
  {
    title: "Grocery",
    body: "The list is built from every meal on this plan, with or without a day. Check items off in the store. Things you always keep on hand show up already checked off.",
  },
  {
    title: "Weekend prep",
    body: "Steps tagged Prep show up here. Chop and batch once; cook fresh later in the week.",
  },
];

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
        if (!hh.prefs?.tour_done) setOpen(true);
      })
      .catch((error) => { throw error; });
    return () => window.removeEventListener("dinnerdesk-tour", start);
  }, []);

  async function finish(saveFilters, stay) {
    setBusy(true);
    try {
      const hh = await api.household();
      const prefs = { ...(hh.prefs || {}), tour_done: true };
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
              <button type="button" className="btn-primary" onClick={() => setStep("eat")}>
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
            <div className="chip-row wrap">
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
            <div className="chip-row wrap">
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
            <div className="chip-row wrap">
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
            <button type="button" className="btn-primary block" onClick={() => setStep("how")}>
              How to use
            </button>
            <button type="button" className="text-link tour-skip" disabled={busy} onClick={() => finish(true)}>
              Save and skip the tour
            </button>
          </>
        )}
        {step === "how" && howStep && (
          <>
            <p className="tour-kicker">
              How to use · {how + 1} of {HOW.length}
            </p>
            <h2 id="tour-title">{howStep.title}</h2>
            <p className="help" data-tip={`tour.how.${how + 1}`}>{howStep.body}</p>
            <TourPicture index={how} />
            {how + 1 < HOW.length ? (
              <button type="button" className="btn-primary block" onClick={() => setHow(how + 1)}>
                Next
              </button>
            ) : (
              <button type="button" className="btn-primary block" disabled={busy} onClick={() => finish(true)}>
                {busy ? "Saving…" : "Start browsing"}
              </button>
            )}
            <button type="button" className="text-link tour-skip" disabled={busy} onClick={() => finish(true)}>
              Skip rest
            </button>
          </>
        )}
      </div>
    </div>
  );
}
