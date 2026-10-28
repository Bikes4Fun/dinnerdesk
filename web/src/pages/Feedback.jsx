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

const MAX_SHOTS = 3;

// A screenshot as a JPEG data URL, at most 2000px on its long side, so phone screenshots stay
// well under the server's 5 MB limit.
function shrink(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, 2000 / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("That file isn't an image we can read.")); };
    img.src = url;
  });
}

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
  const [shots, setShots] = useState([]);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState("");
  const [err, setErr] = useState("");

  function addShots(e) {
    const files = [...e.target.files].slice(0, MAX_SHOTS - shots.length);
    e.target.value = "";
    Promise.all(files.map(shrink))
      .then((added) => setShots((cur) => [...cur, ...added].slice(0, MAX_SHOTS)))
      .catch((error) => setErr(error.message));
  }

  function send(e) {
    e.preventDefault();
    if (!note.trim()) return;
    setBusy(true);
    setErr("");
    api
      .sendFeedback(kind, note.trim(), shots)
      .then(() => {
        setSent(kind);
        setNote("");
        setShots([]);
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
            <div className="feedback-shots">
              {shots.map((src, i) => (
                <div key={i} className="feedback-shot">
                  <img src={src} alt={`Screenshot ${i + 1}`} />
                  <button type="button" aria-label={`Remove screenshot ${i + 1}`}
                    onClick={() => setShots((cur) => cur.filter((_, j) => j !== i))}>✕</button>
                </div>
              ))}
              {shots.length < MAX_SHOTS && (
                <label className="btn-secondary feedback-add-shot">
                  {shots.length ? "Add another screenshot" : "Add a screenshot (optional)"}
                  <input type="file" accept="image/*" multiple hidden onChange={addShots} />
                </label>
              )}
            </div>
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

  const closed = (items || []).filter((i) => i.status === "done" || i.status === "declined").length;
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
            and declined ({closed})
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
                {new Date(item.created_at).toLocaleString()} · {item.version}
              </small>
              {item.behind ? <small className="feedback-behind">Older version ({item.behind})</small> : null}
            </div>
            <p className="feedback-note">{item.note}</p>
            {item.screenshots?.length > 0 && (
              <div className="feedback-shots">
                {item.screenshots.map((src, i) => (
                  <a key={src} href={src} target="_blank" rel="noopener" className="feedback-shot">
                    <img src={src} alt={`Screenshot ${i + 1}`} />
                  </a>
                ))}
              </div>
            )}
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
