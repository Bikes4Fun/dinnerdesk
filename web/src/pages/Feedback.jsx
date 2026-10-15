import { useEffect, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";

// Ids match app/models.py FEEDBACK_KINDS and FEEDBACK_STATUSES.
const KINDS = [
  ["bug", "Report a bug", "Something broke or didn't work the way it should."],
  ["feature", "Suggest a feature", "Something you wish Dinnerdesk did."],
];
const STATUSES = [
  ["new", "New"],
  ["planned", "Planned"],
  ["done", "Done"],
  ["declined", "Declined"],
];
const PLACEHOLDER = {
  bug: "What happened, and what did you expect? e.g. I checked off milk and it came back after a refresh.",
  feature: "e.g. Let me plan lunches too, not just dinners.",
};

function Header({ title, back }) {
  return (
    <header className="top sub">
      <button type="button" className="icon-btn" onClick={() => go(back)} aria-label="Back">
        ←
      </button>
      <h1>{title}</h1>
      <span />
    </header>
  );
}

/** "Report a bug or suggest a feature" (#145). Saved with the app and build that sent it. */
export function Feedback() {
  const [kind, setKind] = useState("bug");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState("");
  const [err, setErr] = useState("");

  function send(e) {
    e.preventDefault();
    if (!note.trim()) return;
    setBusy(true);
    setErr("");
    api
      .sendFeedback(kind, note.trim())
      .then(() => {
        setSent(kind);
        setNote("");
      })
      .catch((error) => setErr(error.message))
      .finally(() => setBusy(false));
  }

  return (
    <section className="screen">
      <Header title="Bugs & ideas" back="/settings" />
      <div className="scroll pad">
        {err && <p className="banner err" role="alert">{err}</p>}
        {sent ? (
          <>
            <p className="banner ok" role="status">
              {sent === "bug" ? "Thanks. We'll look into it." : "Thanks for the idea. We read every one."}
            </p>
            <button type="button" className="btn-secondary block" onClick={() => setSent("")}>
              Send another
            </button>
          </>
        ) : (
          <form className="feedback-form" onSubmit={send}>
            <fieldset>
              <legend className="block-label">What's this about?</legend>
              {KINDS.map(([key, label, help]) => (
                <label key={key} className="feedback-kind">
                  <input type="radio" name="feedback-kind" value={key} checked={kind === key} onChange={() => setKind(key)} />
                  <span>
                    <strong>{label}</strong>
                    <small>{help}</small>
                  </span>
                </label>
              ))}
            </fieldset>
            <label className="block-label" htmlFor="feedback-note">
              {kind === "bug" ? "What went wrong?" : "What would you like?"}
            </label>
            <textarea id="feedback-note" className="field" rows={5} maxLength={2000} value={note}
              placeholder={PLACEHOLDER[kind]} onChange={(e) => setNote(e.target.value)} />
            <button type="submit" className="btn-primary block" disabled={busy || !note.trim()}>
              {busy ? "Sending…" : "Send"}
            </button>
          </form>
        )}
      </div>
    </section>
  );
}

/** Admin: every bug report and feature request, newest first, with where each one stands. */
export function FeedbackInbox() {
  const [items, setItems] = useState(null);
  const [kind, setKind] = useState("all");
  const [showClosed, setShowClosed] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .feedbackList()
      .then((r) => setItems(r.feedback))
      .catch((error) => setErr(error.message));
  }, []);

  function setStatus(item, status) {
    setItems((all) => all.map((i) => (i.id === item.id ? { ...i, status } : i)));
    api.setFeedbackStatus(item.id, status).catch((error) => {
      setErr(error.message);
      setItems((all) => all.map((i) => (i.id === item.id ? { ...i, status: item.status } : i)));
    });
  }

  const shown = (items || []).filter(
    (i) => (kind === "all" || i.kind === kind) && (showClosed || i.status === "new" || i.status === "planned"),
  );

  return (
    <section className="screen">
      <Header title="Bugs & ideas inbox" back="/settings" />
      <div className="scroll pad">
        {err && <p className="banner err" role="alert">{err}</p>}
        <div className="feedback-filters">
          <select className="field" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Show">
            <option value="all">Bugs and ideas</option>
            <option value="bug">Bugs</option>
            <option value="feature">Ideas</option>
          </select>
          <label>
            <input type="checkbox" checked={showClosed} onChange={(e) => setShowClosed(e.target.checked)} /> Show done
            and declined
          </label>
        </div>
        {items === null ? <p className="help">Loading…</p> : null}
        {items !== null && shown.length === 0 ? <p className="help">Nothing here.</p> : null}
        {shown.map((item) => (
          <article className="review-card feedback-item" key={item.id}>
            <div className="feedback-meta">
              <strong>{item.kind === "bug" ? "Bug" : "Idea"}</strong>
              <small>
                {item.email || item.household_name || `Household ${item.household_id}`} ·{" "}
                {new Date(item.created_at).toLocaleString()}
                {item.snapshot?.app ? ` · ${item.snapshot.app}` : ""}
              </small>
            </div>
            <p className="feedback-note">{item.note}</p>
            <select className="field" value={item.status} onChange={(e) => setStatus(item, e.target.value)}
              aria-label="Status">
              {STATUSES.map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </article>
        ))}
      </div>
    </section>
  );
}
