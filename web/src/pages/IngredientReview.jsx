import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";

const TABS = [
  ["easy", "Easy matches"],
  ["harder", "Harder"],
  ["second", "Second pass"],
  ["answered", "Answered"],
];

function Back() {
  return (
    <button type="button" className="icon-btn mob-back" onClick={() => go("/settings")} aria-label="Back">
      ←
    </button>
  );
}

function singularKey(text) {
  const match = text.toLowerCase().match(/^(.*?)([a-z]+)(\s*(?:\([^)]*\))?)$/);
  if (!match) return text.toLowerCase();
  let word = match[2];
  if (word.endsWith("ies")) word = `${word.slice(0, -3)}y`;
  else if (word.endsWith("oes")) word = word.slice(0, -2);
  else if (/(ches|shes|xes|zes)$/.test(word)) word = word.slice(0, -2);
  else if (word.endsWith("s") && !/(ss|us|is)$/.test(word)) word = word.slice(0, -1);
  return `${match[1]}${word}${match[3]}`;
}

function separateBuckets(names) {
  const buckets = new Map();
  names.forEach((name) => {
    const key = singularKey(name.text);
    const bucket = buckets.get(key) || [];
    bucket.push(name);
    buckets.set(key, bucket);
  });
  return [...buckets.values()];
}

function proposedBreakdown(group) {
  const audit = group.audit || {};
  const answer =
    audit.verdict === "suggested_change" && audit.suggested_action
      ? {
          action: audit.suggested_action,
          target: audit.suggested_target,
          names: audit.suggested_names || [],
        }
      : group.answer || {};
  const selected = new Set(answer.names || []);
  const grouped =
    answer.action !== "separate" && selected.size
      ? [
          {
            target: answer.target,
            action: answer.action,
            names: group.names.filter((name) => selected.has(name.text)),
          },
        ]
      : [];
  const remaining =
    answer.action === "separate"
      ? group.names
      : group.names.filter((name) => !selected.has(name.text));
  return { answer, grouped, separate: separateBuckets(remaining) };
}

export function IngredientReview() {
  const [data, setData] = useState({
    groups: [],
    counts: {},
    answered: 0,
    second_review: { total: 0, resolved: 0 },
  });
  const [tab, setTab] = useState("second");
  const [index, setIndex] = useState(0);
  const [target, setTarget] = useState("");
  const [selected, setSelected] = useState([]);
  const [notes, setNotes] = useState("");
  const [showRecipes, setShowRecipes] = useState(false);
  const [recipeName, setRecipeName] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [err, setErr] = useState("");
  const [skipped, setSkipped] = useState(() => {
    try {
      return JSON.parse(window.localStorage.getItem("ingredient-review-v2-skipped") || "[]");
    } catch (error) { throw error; }
  });

  async function load() {
    setData(await api.ingredientReview());
  }

  useEffect(() => {
    load().catch((error) => setErr(error.message));
  }, []);

  useEffect(() => {
    window.localStorage.setItem("ingredient-review-v2-skipped", JSON.stringify(skipped));
  }, [skipped]);

  const visible = useMemo(() => {
    const groups = data.groups.filter((group) =>
      tab === "answered"
        ? group.answer?.status === "answered"
        : tab === "second"
          ? group.answer?.status === "answered" &&
            group.audit?.verdict &&
            group.audit?.review_status !== "removed"
        : group.queue === tab && group.answer?.status !== "answered",
    );
    if (tab === "answered") return groups;
    if (tab === "second") {
      const statusRank = { pending: 0, re_review: 1, resolved: 2 };
      const verdictRank = { suggested_change: 0, question: 1, looks_good: 2 };
      return [...groups].sort((a, b) => {
        const statusDifference =
          (statusRank[a.audit?.review_status] ?? 0) -
          (statusRank[b.audit?.review_status] ?? 0);
        if (statusDifference) return statusDifference;
        return (
          (verdictRank[a.audit?.verdict] ?? 1) -
          (verdictRank[b.audit?.verdict] ?? 1)
        );
      });
    }
    return [...groups].sort((a, b) => {
      const aIndex = skipped.indexOf(a.id);
      const bIndex = skipped.indexOf(b.id);
      if (aIndex < 0 && bIndex >= 0) return -1;
      if (aIndex >= 0 && bIndex < 0) return 1;
      if (aIndex >= 0 && bIndex >= 0) return aIndex - bIndex;
      return 0;
    });
  }, [data.groups, skipped, tab]);
  const group = visible[Math.min(index, Math.max(visible.length - 1, 0))];

  useEffect(() => {
    setIndex(0);
  }, [tab]);

  useEffect(() => {
    if (!group) return;
    const answer = group.answer || {};
    setTarget(answer.target || group.suggested_name);
    setSelected(
      answer.names?.length
        ? answer.names
        : group.queue === "easy"
          ? group.names.map((name) => name.text)
          : [],
    );
    setNotes(answer.notes || "");
    setShowRecipes(false);
    setRecipeName("");
    setMessage("");
  }, [group?.id, tab]);

  useEffect(() => {
    if (!group || notes === (group.answer?.notes || "")) return undefined;
    const timer = window.setTimeout(() => {
      api
        .putIngredientReviewNotes(group.id, notes)
        .catch(() => setErr("Couldn’t save notes"));
    }, 650);
    return () => window.clearTimeout(timer);
  }, [group?.id, group?.answer?.notes, notes]);

  function toggleSelected(name) {
    setSelected((current) =>
      current.includes(name) ? current.filter((item) => item !== name) : [...current, name],
    );
  }

  async function saveAnswer(action) {
    if (!group || !target.trim()) return;
    setSaving(true);
    setErr("");
    try {
      await api.putIngredientReviewNotes(group.id, notes);
      await api.putIngredientReviewAnswer(group.id, {
        action,
        target: target.trim(),
        names: action === "separate" ? [] : selected,
      });
      if (tab === "second") {
        await api.putIngredientReviewAuditResolution(group.id, "revised");
      }
      setSkipped((current) => current.filter((id) => id !== group.id));
      await load();
      setIndex(0);
      setMessage("Answer saved for final review. No recipes were changed.");
    } catch (error) {
      setErr(error.message);
    } finally {
      setSaving(false);
    }
  }

  async function skipCurrent() {
    if (!group) return;
    try {
      await api.putIngredientReviewNotes(group.id, notes);
    } catch {
      setErr("Couldn’t save notes");
      return;
    }
    if (tab === "second") {
      setIndex((current) => Math.min(current + 1, visible.length - 1));
      return;
    }
    setSkipped((current) => (current.includes(group.id) ? current : [...current, group.id]));
    setIndex(0);
  }

  async function resolveSecondPass(resolution) {
    if (!group) return;
    setSaving(true);
    setErr("");
    try {
      await api.putIngredientReviewNotes(group.id, notes);
      if (resolution === "accepted_suggestion") {
        const audit = group.audit;
        await api.putIngredientReviewAnswer(group.id, {
          action: audit.suggested_action,
          target: audit.suggested_target,
          names: audit.suggested_action === "separate" ? [] : audit.suggested_names,
        });
      }
      await api.putIngredientReviewAuditResolution(group.id, resolution);
      await load();
      setIndex(0);
      setMessage(
        resolution === "re_review"
          ? "Saved for re-review and moved behind the pending items."
          : "Revision confirmed for final review. No recipes were changed.",
      );
    } catch (error) {
      setErr(error.message);
    } finally {
      setSaving(false);
    }
  }

  const canGroup =
    group &&
    selected.length > 0 &&
    new Set([target.trim().toLowerCase(), ...selected.map((name) => name.toLowerCase())]).size > 1;
  const recipeExamples = recipeName
    ? group?.names.find((name) => name.text === recipeName)?.recipes || []
    : group?.recipes || [];
  const breakdown = group ? proposedBreakdown(group) : null;

  return (
    <section className="screen">
      <header className="top sub">
        <Back />
        <h1>Ingredient review</h1>
        <span />
      </header>

      <div className="chip-row">
        {TABS.map(([id, label]) => (
          <button
            type="button"
            className={`chip${tab === id ? " is-on" : ""}`}
            onClick={() => {
              setTab(id);
              setIndex(0);
              setErr("");
            }}
            key={id}
          >
            {label}{" "}
            {id === "answered"
              ? data.answered
              : id === "second"
                ? `${data.second_review?.resolved || 0}/${data.second_review?.total || 0}`
                : data.counts[id] || 0}
          </button>
        ))}
      </div>

      <div className="scroll pad ingredient-review">
        <p className="banner review-only">
          Answers only — this page never changes recipes or the live ingredient database.
        </p>
        {err ? <p className="banner err">{err}</p> : null}
        {message ? <p className="banner ok">{message}</p> : null}

        {!group ? (
          <div className="empty-block">Nothing left in this section.</div>
        ) : (
          <article className="review-card">
            <div className="review-progress">
              <span>
                {tab === "second"
                  ? "Second-pass audit of your saved answer"
                  : "Possible match from all three recipe archives"}
              </span>
              <span>
                {index + 1} of {visible.length}
              </span>
            </div>

            {group.answer?.status === "answered" && tab !== "second" ? (
              <p className="review-answer-summary">
                Saved: {group.answer.action} → {group.answer.target}
              </p>
            ) : null}

            {tab === "second" ? (
              <div className={`review-audit review-audit-${group.audit.verdict}`}>
                <strong>
                  {group.audit.verdict === "looks_good"
                    ? "Looks good"
                    : group.audit.verdict === "suggested_change"
                      ? "Suggested correction"
                      : "Question"}
                </strong>
                <p>{group.audit.reason}</p>
                {group.audit.review_status === "resolved" ? (
                  <small>Second pass completed: {group.audit.resolution}</small>
                ) : group.audit.review_status === "re_review" ? (
                  <small>Saved for another review</small>
                ) : null}
              </div>
            ) : null}

            {tab === "second" ? (
              <section className="review-breakdown">
                <h2>Proposed result</h2>
                {breakdown.grouped.map((result) => (
                  <div className="review-result-group" key={`${result.action}-${result.target}`}>
                    <span className="review-result-label">
                      {result.action === "alias"
                        ? "Same grocery item · keep recipe wording"
                        : "Recipes would use"}
                    </span>
                    <strong>{result.target}</strong>
                    <div className="review-result-forms">
                      {result.names.map((name) => (
                        <button
                          type="button"
                          className="review-result-form"
                          onClick={() => {
                            setRecipeName(name.text);
                            setShowRecipes(true);
                          }}
                          key={name.text}
                        >
                          {name.text} <small>{name.count} uses · view</small>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
                {breakdown.separate.map((bucket) => {
                  const primary = [...bucket].sort((a, b) => b.count - a.count)[0];
                  return (
                    <div className="review-result-group is-separate" key={singularKey(primary.text)}>
                      <span className="review-result-label">
                        {breakdown.answer.action === "separate"
                          ? "Separate grocery item"
                          : "Not included in that group"}
                      </span>
                      <strong>{primary.text}</strong>
                      <div className="review-result-forms">
                        {bucket.map((name) => (
                          <button
                            type="button"
                            className="review-result-form"
                            onClick={() => {
                              setRecipeName(name.text);
                              setShowRecipes(true);
                            }}
                            key={name.text}
                          >
                            {name.text} <small>{name.count} uses · view</small>
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </section>
            ) : (
              <fieldset className="review-options">
                <legend>Which names belong together?</legend>
                <p className="help" data-tip="ingredient-review.merge">Check only the names that mean the same grocery item.</p>
                {group.names.map((name) => (
                  <div className="review-option" key={name.text}>
                    <input
                      type="checkbox"
                      aria-label={`Include ${name.text}`}
                      checked={selected.includes(name.text)}
                      onChange={() => toggleSelected(name.text)}
                    />
                    <span>{name.text}</span>
                    <button
                      type="button"
                      className="review-source-count"
                      onClick={() => {
                        setRecipeName(name.text);
                        setShowRecipes(true);
                      }}
                    >
                      {name.count} uses ·{" "}
                      {Object.entries(name.sources)
                        .map(([source, count]) => `${source} ${count}`)
                        .join(" · ")}
                      {" · view"}
                    </button>
                    <label className="review-target">
                      <input
                        type="radio"
                        name={`target-${group.id}`}
                        checked={target === name.text}
                        onChange={() => {
                          setTarget(name.text);
                          setSelected((current) =>
                            current.includes(name.text) ? current : [...current, name.text],
                          );
                        }}
                      />
                      Use name
                    </label>
                  </div>
                ))}

                <label className="block-label" htmlFor="custom-ingredient-name">
                  Or type another name
                </label>
                <input
                  id="custom-ingredient-name"
                  className="field-input"
                  value={target}
                  onChange={(event) => setTarget(event.target.value)}
                />
              </fieldset>
            )}

            <label className="block-label" htmlFor="ingredient-review-notes">
              {tab === "second" ? "Notes if this needs another review" : "Notes for later"}
            </label>
            <textarea
              id="ingredient-review-notes"
              className="field dev-notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              onBlur={() =>
                api
                  .putIngredientReviewNotes(group.id, notes)
                  .catch(() => setErr("Couldn’t save notes"))
              }
              placeholder="Add context or something to check before applying changes…"
            />

            <button
              type="button"
              className="text-link review-recipes-toggle"
              onClick={() => {
                setRecipeName("");
                setShowRecipes((current) => !current);
              }}
            >
              {showRecipes ? "Hide recipe examples" : "Show all recipe examples"}
            </button>

            {showRecipes ? (
              <div className="review-recipes">
                {recipeName ? <strong className="review-recipes-title">Examples for “{recipeName}”</strong> : null}
                {recipeExamples.map((recipe, recipeIndex) =>
                  recipe.source_url ? (
                    <a
                      className="review-recipe"
                      href={recipe.source_url}
                      target="_blank"
                      rel="noreferrer"
                      key={`${recipe.source}-${recipe.name}-${recipeIndex}`}
                    >
                      <strong>{recipe.name}</strong>
                      <small>
                        {recipe.source} · “{recipe.raw}”
                      </small>
                    </a>
                  ) : (
                    <div
                      className="review-recipe"
                      key={`${recipe.source}-${recipe.name}-${recipeIndex}`}
                    >
                      <strong>{recipe.name}</strong>
                      <small>
                        {recipe.source} · “{recipe.raw}”
                      </small>
                    </div>
                  ),
                )}
              </div>
            ) : null}

            <div className="review-actions">
              {tab === "second" ? (
                <>
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={saving}
                    onClick={() =>
                      resolveSecondPass(
                        group.audit.suggested_action ? "accepted_suggestion" : "confirmed",
                      )
                    }
                  >
                    Confirm this revision
                  </button>
                  <button
                    type="button"
                    className="btn-secondary review-wide"
                    disabled={saving}
                    onClick={() => resolveSecondPass("re_review")}
                  >
                    Save for re-review
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={saving || !canGroup}
                    onClick={() => saveAnswer("standardize")}
                  >
                    Suggest changing selected to this
                  </button>
                  <button
                    type="button"
                    className="btn-secondary review-wide"
                    disabled={saving || !canGroup}
                    onClick={() => saveAnswer("alias")}
                  >
                    Same item, keep recipe wording
                  </button>
                  <button
                    type="button"
                    className="review-separate"
                    disabled={saving}
                    onClick={() => saveAnswer("separate")}
                  >
                    Keep all separate
                  </button>
                </>
              )}
            </div>
          </article>
        )}

        {visible.length > 1 ? (
          <div className="review-nav">
            <button
              type="button"
              className="btn-secondary"
              disabled={index === 0}
              onClick={() => setIndex((current) => Math.max(0, current - 1))}
            >
              Previous
            </button>
            <button type="button" className="btn-secondary" onClick={skipCurrent}>
              {tab === "second" ? "Next" : "Skip for now"}
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
