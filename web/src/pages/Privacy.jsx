import { useEffect, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";
import { Copy } from "../Copy.js";
import { PrivacySummary } from "../PrivacySummary.jsx";

const CLEARABLE = [
  ["taste_lab", "Taste Lab history", "Your likes and passes in Taste Lab. Your filters stay in Settings."],
  ["meal_ratings", "Meal ratings", "Thumbs up or down on planned meals, for the whole household."],
  ["prep_votes", "Prep votes", "Thumbs up or down on prep steps, and steps you added, for the whole household."],
];

/** "Download my data", plus clearing parts of it (#101). */
function YourData() {
  const [signedIn, setSignedIn] = useState(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const [partial, setPartial] = useState(false);

  useEffect(() => {
    api.auth.status().then((s) => setSignedIn(s.authenticated)).catch(() => setSignedIn(false));
  }, []);

  async function run(work) {
    setErr("");
    setNote("");
    setBusy(true);
    try {
      await work();
    } catch (e) {
      setErr((e.body && e.body.message) || e.message);
    } finally {
      setBusy(false);
    }
  }

  const download = () => run(async () => {
    const data = await api.exportData();
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `dinnerdesk-data-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setPartial(data.complete === false);
  });

  const clear = (kind, label) => {
    if (!window.confirm(`Clear your ${label.toLowerCase()}? This can’t be undone.`)) return;
    run(async () => {
      await api.clearData([kind]);
      setNote(`${label} cleared.`);
    });
  };

  const deleteKitchen = () => {
    if (!window.confirm("Delete this kitchen from our server? Plans, pantry, grocery lists, ratings and Taste Lab answers are removed. It can’t be undone.")) return;
    run(async () => {
      await api.deleteGuestKitchen();
      window.location.assign("/");
    });
  };

  return (
    <>
      <h2>Your data</h2>
      <p>
        Get a copy of everything we store for your household: plans, grocery lists, pantry, filters, ratings,
        prep votes, Taste Lab answers and the recipes you added. Passwords and sign-in tokens are never included.
      </p>
      <p><button type="button" className="btn-secondary" disabled={busy} onClick={download}>Download my data</button></p>
      {partial && (
        <p className="banner err" role="alert">
          Taste Lab was unavailable, so this file is missing your Taste Lab answers.{" "}
          <button type="button" className="text-link" disabled={busy} onClick={download}>Try again</button>
        </p>
      )}

      <h2>Clear part of your data</h2>
      <p>Clear one kind of data and keep the rest of your kitchen and your account. Only the household creator or an admin can clear the household’s ratings and prep votes.</p>
      {CLEARABLE.map(([kind, label, about]) => (
        <p key={kind}>
          <button type="button" className="btn-secondary danger" disabled={busy} onClick={() => clear(kind, label)}>Clear {label.toLowerCase()}</button>
          <br /><span className="help">{about}</span>
        </p>
      ))}
      {signedIn === false && (
        <p>
          <button type="button" className="btn-secondary danger" disabled={busy} onClick={deleteKitchen}>Delete this kitchen</button>
          <br /><span className="help">Removes this guest kitchen from our server, not just from this browser.</span>
        </p>
      )}
      {note && <p className="banner ok" role="status">{note}</p>}
      {err && <p className="banner err" role="alert">{err}</p>}
    </>
  );
}

export function Privacy() {
  return (
    <div className="app">
    <section className="screen">
      <header className="top">
        <button type="button" className="icon-btn" onClick={() => (window.history.length > 1 ? window.history.back() : go("/"))} aria-label="Back">
          ←
        </button>
        <h1>Privacy</h1>
      </header>
      <div className="scroll pad privacy">
        <p>{Copy.text("privacy.intro")}</p>

        <PrivacySummary />

        <YourData />

        <h2 className="privacy-details">{Copy.text("privacy.details.title")}</h2>

        <p>{Copy.text("privacy.policy.intro")}</p>
        {Copy.steps("privacy.policy", Number(Copy.text("privacy.policy.count"))).map((section, i) => (
          <div key={`policy-${i}`}>
            <h2>{section.title}</h2>
            {section.body.split("\n\n").map((paragraph, j) => <p key={j}>{paragraph}</p>)}
          </div>
        ))}

        <h2>Questions</h2>
        <p>
          See <a className="text-link" href="/support" onClick={(e) => { e.preventDefault(); go("/support"); }}>Help &amp; support</a> to contact us.
        </p>
      </div>
    </section>
    </div>
  );
}
