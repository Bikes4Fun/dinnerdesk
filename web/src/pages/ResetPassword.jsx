import { useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";

function friendlyError(e) {
  return (e && e.body && e.body.message) || (e && e.message) || "Something went wrong.";
}

/** Opened from the emailed link: /reset/<token>. */
export function ResetPassword({ token, onAuthed }) {
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr("");
    if (password !== again) {
      setErr("Passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await api.auth.resetPassword({ token, password });
      setDone(true);
    } catch (e) {
      setErr(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app is-auth">
      <section className="screen auth-screen">
        <div className="scroll pad auth-pad">
          <div className="brand auth-brand">Dinnerdesk</div>
          <h1 className="auth-title">Set a new password</h1>
          {err ? <p className="banner err">{err}</p> : null}
          {done ? (
            <>
              <p className="banner ok">
                Password changed. You're signed in here; use the new password in the app too.
              </p>
              <button type="button" className="btn-primary block" onClick={() => onAuthed()}>
                Continue
              </button>
            </>
          ) : (
            <form onSubmit={submit}>
              <label className="block-label" htmlFor="new_password">
                New password
              </label>
              <input
                id="new_password"
                className="field"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
              <label className="block-label" htmlFor="new_password_again">
                Type it again
              </label>
              <input
                id="new_password_again"
                className="field"
                type="password"
                required
                minLength={8}
                value={again}
                onChange={(e) => setAgain(e.target.value)}
                autoComplete="new-password"
              />
              <p className="help">At least 8 characters.</p>
              <button type="submit" className="btn-primary block" disabled={busy}>
                {busy ? "Saving…" : "Save new password"}
              </button>
              <button type="button" className="text-link" onClick={() => go("/login")}>
                Back to sign in
              </button>
            </form>
          )}
        </div>
      </section>
    </div>
  );
}
