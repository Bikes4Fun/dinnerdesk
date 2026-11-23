import { useState } from "react";
import { Copy } from "../Copy.js";
import { go } from "../nav.js";

const NOTE_SEEN = "dd_tastelab_privacy_note";

function noteDismissed() {
  try {
    return window.localStorage.getItem(NOTE_SEEN) === "1";
  } catch {
    return false;
  }
}

/** A reminder where the data is made: what Taste Lab keeps. Dismissed once per browser. */
function PrivacyNote() {
  const [hidden, setHidden] = useState(noteDismissed);
  if (hidden) return null;
  const dismiss = () => {
    try {
      window.localStorage.setItem(NOTE_SEEN, "1");
    } catch {
      /* private mode: it just shows again next time */
    }
    setHidden(true);
  };
  return (
    <aside className="taste-privacy-note">
      <p>
        {Copy.text("privacy.tastelab.note")}{" "}
        <a className="text-link" href="/privacy" onClick={(e) => { e.preventDefault(); go("/privacy"); }}>
          {Copy.text("privacy.tastelab.link")}
        </a>
      </p>
      <button type="button" className="icon-btn" aria-label="Dismiss note" onClick={dismiss}>×</button>
    </aside>
  );
}

export function TasteLab() {
  const search = new URLSearchParams(window.location.search);
  const frame = new URLSearchParams();
  frame.set("chrome", "app");
  if (search.get("swipe") === "1") frame.set("swipe", "1");
  const src = `/tastelab/?${frame.toString()}`;
  return (
    <section className="screen taste-lab-screen">
      <header className="top sub">
        <button
          type="button"
          className="icon-btn mob-back"
          aria-label="Back"
          onClick={() => {
            if (window.history.state) window.history.back();
            else go("/more");
          }}
        >
          ←
        </button>
        <h1>Taste Lab</h1>
        <span />
      </header>
      <PrivacyNote />
      <iframe key={src} className="taste-frame" title="Taste Lab" src={src} />
    </section>
  );
}
