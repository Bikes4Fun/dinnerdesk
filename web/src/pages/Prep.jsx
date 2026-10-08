import { useEffect, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";
import { Thumbs } from "../Thumbs.jsx";

export function Prep() {
  const [tasks, setTasks] = useState([]);
  const [err, setErr] = useState("");

  async function load() {
    const plan = await api.plan();
    const data = await api.prep(plan.id);
    setTasks(data.tasks);
  }

  useEffect(() => {
    load().catch((e) => setErr(e.message));
  }, []);

  async function toggle(task) {
    const done = !task.done;
    // Checking a task checks every item in it.
    setTasks((cur) => cur.map((t) => (t.id !== task.id ? t : {
      ...t, done, meals: t.meals.map((m) => ({ ...m, steps: (m.steps || []).map((s) => ({ ...s, done })) })),
    })));
    try {
      await api.patchPrep(task.id, done);
      await load();
    } catch (e) {
      setErr(e.message);
      load();
    }
  }

  async function toggleItem(task, meal, step) {
    const done = !step.done;
    setTasks((cur) => cur.map((t) => {
      if (t.id !== task.id) return t;
      const meals = t.meals.map((m) => m.id !== meal.id ? m : {
        ...m, steps: m.steps.map((s) => (s.key === step.key ? { ...s, done } : s)),
      });
      return { ...t, meals, done: meals.every((m) => (m.steps || []).every((s) => s.done)) };
    }));
    try {
      await api.checkPrepItem(task.id, { recipe_id: meal.id, key: step.key, done });
    } catch (e) {
      setErr(e.message);
      load();
    }
  }

  function summary(t) {
    const names = t.meals.map((m) => m.name).join(", ");
    const steps = t.meals.flatMap((m) => m.steps || []);
    const done = steps.filter((s) => s.done).length;
    return steps.length > 1 && done > 0 && done < steps.length
      ? `For ${names} · ${done} of ${steps.length} done`
      : `For ${names}`;
  }

  async function rateStep(task, meal, step, rating) {
    const set = (r) => setTasks((cur) => cur.map((t) => t.id !== task.id ? t : {
      ...t,
      meals: t.meals.map((m) => m.id !== meal.id ? m : {
        ...m, steps: m.steps.map((s) => s.key === step.key ? { ...s, rating: r } : s),
      }),
    }));
    const before = step.rating || 0;
    set(rating);
    try {
      await api.ratePrepStep({ recipe_id: meal.id, key: step.key, text: step.text, category: task.title, auto: step.auto !== false, rating });
    } catch (e) {
      set(before);
      setErr(e.message);
    }
  }

  const stepNote = (step) =>
    step.rating > 0 ? "Useful ahead" : step.rating < 0 ? "Not useful ahead" : "Useful to do ahead?";

  return (
    <section className="screen">
      <header className="top">
        <button type="button" className="icon-btn mob-back" onClick={() => go("/more")} aria-label="Back">
          ←
        </button>
        <h1>Weekend prep</h1>
      </header>
      <div className="scroll pad">
        {err && <p className="banner err">{err}</p>}
        <p className="help" data-tip="prep.about">
          Built from this plan’s meals. Chop and batch now; cook fresh later in the week.
        </p>
        {tasks.length === 0 ? (
          <>
            <p className="muted" data-tip="prep.empty">No prep yet. Add meals on Plan. Make-ahead steps like chopping, grating and sauces show up here.</p>
            <button type="button" className="btn-secondary" onClick={() => go("/")}>
              Back to plan
            </button>
          </>
        ) : (
          <ul className="task-list">
            {tasks.map((t) => (
              <li key={t.id}>
                <button type="button" className="check" aria-pressed={t.done} aria-label={t.done ? `Mark ${t.title} not done` : `Mark all of ${t.title} done`} onClick={() => toggle(t)}>
                  {t.done ? "✓" : ""}
                </button>
                <details className={t.done ? "is-checked" : ""}>
                  <summary><strong>{t.title}</strong><div className="muted">{summary(t)}</div>{t.auto && <div className="prep-suggested">Suggested from your recipes</div>}</summary>
                  {t.quantities.map((q) => <div key={q} className="muted">{q}</div>)}
                  {t.meals.map((meal) => <div key={meal.id} className="prep-meal">
                    <button className="text-link" onClick={() => go(`/recipes/${meal.id}`)}>{meal.name}</button>
                    {meal.steps?.length
                      ? meal.steps.map((step) => <div key={step.key} className="prep-step">
                          <label style={{ display: "flex", gap: 8, alignItems: "start" }}><input type="checkbox" checked={!!step.done} onChange={() => toggleItem(t, meal, step)} /><span style={{ whiteSpace: "pre-wrap", textDecoration: step.done ? "line-through" : "none" }}>{step.text}</span></label>
                          <span className="meal-thumbs">
                            <Thumbs size={16} rating={step.rating || 0} subject="this prep step" onRate={(r) => rateStep(t, meal, step, r)} />
                            <span className="muted">{stepNote(step)}</span>
                          </span>
                        </div>)
                      : meal.instructions.map((text, i) => <p key={i} style={{ whiteSpace: "pre-wrap" }}>{text}</p>)}
                  </div>)}
                </details>
              </li>
            ))}
            </ul>
          )}
          <button type="button" className="list-foot-link" onClick={() => window.print()}>
            Print prep
          </button>
        </div>
      </section>
    );
  }
