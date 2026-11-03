import { useEffect, useRef, useState } from "react";
import FoodPhoto from "./FoodPhoto.jsx";
import { Icon } from "./icons.jsx";
import { go } from "./nav.js";
import { useWeek } from "./week.jsx";
import { planStripScrollPosition } from "./planStripScroll.js";

const HIDE_KEY = "dd.planStrip.hidden";

function readHidden() {
  try {
    return window.localStorage.getItem(HIDE_KEY) === "1";
  } catch {
    return false;
  }
}

function saveHidden(on) {
  try {
    if (on) window.localStorage.setItem(HIDE_KEY, "1");
    else window.localStorage.removeItem(HIDE_KEY);
  } catch {
    /* storage blocked: the choice lasts until reload */
  }
}

/** Small carousel of this week's meals, pinned under the recipe list while browsing. */
export function PlanStrip() {
  const week = useWeek();
  const [hidden, setHidden] = useState(readHidden);
  const trackRef = useRef(null);
  const plan = week?.plan;
  const slots = plan?.slots || [];
  const count = slots.length;
  const previousPlan = useRef(null);

  // Reset a reused track on a different week; reveal the newest meal after an add.
  useEffect(() => {
    const position = planStripScrollPosition(previousPlan.current, plan);
    if (position && trackRef.current) {
      trackRef.current.scrollTo({
        left: position === "start" ? 0 : trackRef.current.scrollWidth,
        behavior: position === "start" ? "auto" : "smooth",
      });
    }
    previousPlan.current = plan;
  }, [plan]);

  if (!count) return null;

  function setHide(on) {
    setHidden(on);
    saveHidden(on);
  }

  if (hidden) {
    return (
      <div className="plan-strip is-collapsed">
        <button type="button" className="plan-strip-pill" onClick={() => setHide(false)} aria-label={`Show this week's meals (${count})`}>
          <Icon name="plan" size={16} /> This week · {count}
        </button>
      </div>
    );
  }

  return (
    <section className="plan-strip" aria-label="This week's meals">
      <div className="plan-strip-head">
        <button type="button" className="text-link" onClick={() => go("/")}>
          This week · {count}
        </button>
        <button type="button" className="icon-btn plan-strip-close" onClick={() => setHide(true)} aria-label="Hide this week's meals">
          <Icon name="close" size={16} />
        </button>
      </div>
      <ul className="plan-strip-track" ref={trackRef}>
        {slots.map((s) => (
          <li key={s.id} className={s.cooked ? "is-cooked" : undefined}>
            <button type="button" className="plan-strip-open" onClick={() => go(`/recipes/${s.recipe_id}`)} aria-label={`Open ${s.recipe_name}`}>
              <FoodPhoto path={s.photo_path} />
              <span className="plan-strip-name">{s.recipe_name}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
