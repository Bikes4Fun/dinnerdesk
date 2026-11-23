import { useEffect, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";
import { Copy } from "../Copy.js";
import { PrivacySummary } from "../PrivacySummary.jsx";

const CLEARABLE = [
  ["taste_lab", Copy.text("ui.taste.lab.history"), Copy.text("ui.your.likes.and.passes.in")],
  ["meal_ratings", Copy.text("privacy.short.keep.4"), Copy.text("ui.thumbs.up.or.down.on")],
  ["prep_votes", Copy.text("ui.prep.votes"), Copy.text("ui.thumbs.up.or.down.on.2")],
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
    if (!window.confirm(Copy.text("ui.delete.this.kitchen.from.our"))) return;
    run(async () => {
      await api.deleteGuestKitchen();
      window.location.assign("/");
    });
  };

  return (
    <>
      <h2>{Copy.text("ui.your.data")}</h2>
      <p>
        Get a copy of everything we store for your household: plans, grocery lists, pantry, filters, ratings,
        prep votes, Taste Lab answers and the recipes you added. Passwords and sign-in tokens are never included.
      </p>
      <p><button type="button" className="btn-secondary" disabled={busy} onClick={download}>{Copy.text("ui.download.my.data")}</button></p>
      {partial && (
        <p className="banner err" role="alert">
          Taste Lab was unavailable, so this file is missing your Taste Lab answers.{" "}
          <button type="button" className="text-link" disabled={busy} onClick={download}>{Copy.text("ui.try.again")}</button>
        </p>
      )}

      <h2>{Copy.text("ui.clear.part.of.your.data")}</h2>
      <p>{Copy.text("ui.clear.one.kind.of.data")}</p>
      {CLEARABLE.map(([kind, label, about]) => (
        <p key={kind}>
          <button type="button" className="btn-secondary danger" disabled={busy} onClick={() => clear(kind, label)}>Clear {label.toLowerCase()}</button>
          <br /><span className="help">{about}</span>
        </p>
      ))}
      {signedIn === false && (
        <p>
          <button type="button" className="btn-secondary danger" disabled={busy} onClick={deleteKitchen}>{Copy.text("ui.delete.this.kitchen")}</button>
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
