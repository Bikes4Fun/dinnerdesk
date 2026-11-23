import { useState } from "react";
import { api } from "./api.js";
import { Copy } from "./Copy.js";
import { go } from "./nav.js";
import { PrivacySummary } from "./PrivacySummary.jsx";

/**
 * The first-open privacy screen. Shows until this guest kitchen (or account) agrees to the current
 * privacy version (/api/auth/status privacy_agreed). "I understand, continue" is the agreement.
 * Same screen as iOS PrivacyAgreementView and Android PrivacyAgreement.
 */
export function PrivacyAgreement({ signedIn, onAgreed }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function agree() {
    setErr("");
    setBusy(true);
    try {
      await api.agreeToPrivacy();
      onAgreed();
    } catch (e) {
      setErr((e.body && e.body.message) || e.message || "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <div className="app is-auth">
      <section className="screen auth-screen">
        <div className="scroll pad auth-pad privacy-agreement">
          <div className="brand auth-brand">{Copy.text("app.name")}</div>
          <h1 className="auth-title">{Copy.text("privacy.agree.title")}</h1>
          <p>{Copy.text(signedIn ? "privacy.agree.updated" : "privacy.agree.guest")}</p>

          <PrivacySummary compact />

          {!signedIn && <p className="privacy-device-note">{Copy.text("privacy.agree.device")}</p>}
          {err && <p className="banner err" role="alert">{err}</p>}

          <button type="button" className="btn-primary block" disabled={busy} onClick={agree}>
            {Copy.text("privacy.agree.button")}
          </button>
          <p className="help privacy-fine">{Copy.text("privacy.agree.fine")}</p>
          <button type="button" className="text-link" onClick={() => go("/privacy")}>
            {Copy.text("privacy.agree.read")}
          </button>
          {!signedIn && (
            <button type="button" className="text-link" onClick={() => go("/login")}>
              Create an account instead
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
