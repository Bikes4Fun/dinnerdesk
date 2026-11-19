import { useId } from "react";
import { Tip } from "./Tip.jsx";

function stepKey() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function emptyStep() {
  return { key: stepKey(), text: "", prep: false, ings: "" };
}

export function stepsFromRecipe(instructions) {
  return (instructions || []).map((s) => ({
    key: stepKey(),
    text: s.text || s.step || "",
    prep: !!s.prep,
    ings: (s.ings || "").replace(/\r\n/g, "\n"),
  }));
}

export function serializeSteps(steps) {
  return steps
    .map((s) => ({
      text: s.text.trim(),
      prep: !!s.prep,
      ings: (s.ings || "").replace(/\r\n/g, "\n").trim(),
    }))
    .filter((s) => s.text);
}

export function RecipeEditorFields({
  name,
  setName,
  servings,
  setServings,
  minutes,
  setMinutes,
  ings,
  setIngs,
  steps,
  setSteps,
  help,
}) {
  const fieldId = useId();

  function moveStep(i, delta) {
    const j = i + delta;
    if (j < 0 || j >= steps.length) return;
    const next = steps.slice();
    const [item] = next.splice(i, 1);
    next.splice(j, 0, item);
    setSteps(next);
  }

  return (
    <>
      {help ? <Tip id="recipe-editor.intro">{help}</Tip> : null}
      <label className="block-label" htmlFor={`${fieldId}-name`}>Name</label>
      <input id={`${fieldId}-name`} className="field" required value={name} onChange={(e) => setName(e.target.value)} />
      <label className="block-label" htmlFor={`${fieldId}-servings`}>Servings</label>
      <input
        className="field"
        id={`${fieldId}-servings`}
        type="number"
        min="1"
        value={servings}
        onChange={(e) => setServings(e.target.value)}
      />
      <label className="block-label" htmlFor={`${fieldId}-minutes`}>Minutes</label>
      <input
        className="field"
        id={`${fieldId}-minutes`}
        type="number"
        min="0"
        value={minutes}
        onChange={(e) => setMinutes(e.target.value)}
      />
      <label className="block-label" htmlFor={`${fieldId}-ingredients`}>Ingredients (one per line)</label>
      <textarea id={`${fieldId}-ingredients`} className="field" rows={10} value={ings} onChange={(e) => setIngs(e.target.value)} />
      <h2 className="block-label">Steps</h2>
      <Tip id="recipe-editor.steps">
        `- ` starts a bullet. Amounts for this step are the list under the instruction on Cook. Empty amounts is fine.
      </Tip>
      {steps.map((s, i) => (
        <div key={s.key} className="step-edit">
          <div className="step-edit-head">
            <span className="step-num">Step {i + 1}</span>
            <div className="step-edit-actions">
              <button
                type="button"
                className="step-move"
                disabled={i === 0}
                aria-label={`Move step ${i + 1} up`}
                onClick={() => moveStep(i, -1)}
              >
                ↑
              </button>
              <button
                type="button"
                className="step-move"
                disabled={i === steps.length - 1}
                aria-label={`Move step ${i + 1} down`}
                onClick={() => moveStep(i, 1)}
              >
                ↓
              </button>
              <label className="prep-toggle">
                <input
                  type="checkbox"
                  aria-label={`Prep step ${i + 1} ahead`}
                  checked={!!s.prep}
                  onChange={(e) =>
                    setSteps(steps.map((x, j) => (j === i ? { ...x, prep: e.target.checked } : x)))
                  }
                />
                Prep
              </label>
              <button type="button" className="step-remove" aria-label={`Remove step ${i + 1}`}
                onClick={() => setSteps(steps.filter((x) => x.key !== s.key))}>Remove</button>
            </div>
          </div>
          <textarea
            aria-label={`Step ${i + 1} instructions`}
            className="field step-text"
            rows={Math.max(4, s.text.split("\n").length + 1)}
            value={s.text}
            onChange={(e) => setSteps(steps.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
          />
          <label className="block-label step-ings-label" htmlFor={`${fieldId}-step-ings-${s.key}`}>
            Amounts for step {i + 1}
          </label>
          <textarea
            id={`${fieldId}-step-ings-${s.key}`}
            className="field step-ings-edit"
            rows={Math.max(2, (s.ings || "").split("\n").length)}
            placeholder="6 tbsp olive oil"
            value={s.ings}
            onChange={(e) => setSteps(steps.map((x, j) => (j === i ? { ...x, ings: e.target.value } : x)))}
          />
        </div>
      ))}
      <button type="button" className="btn-secondary" onClick={() => setSteps([...steps, emptyStep()])}>
        Add step
      </button>
    </>
  );
}
