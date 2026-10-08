import { useEffect, useState } from "react";
import { api } from "../api.js";

function friendlyError(e) {
  return (e && e.body && e.body.message) || (e && e.message) || "Something went wrong.";
}

export function AcceptInvite({ token, onAuthed }) {
  const [preview, setPreview] = useState(null);
  const [previewErr, setPreviewErr] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.previewInvite(token).then(setPreview).catch((e) => setPreviewErr(friendlyError(e)));
  }, [token]);

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await api.acceptInvite({ token, email, password });
      const me = await api.auth.me();
      onAuthed(me);
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

          {previewErr ? (
            <p className="banner err">{previewErr}</p>
          ) : !preview ? (
            <p className="help">Loading invite…</p>
          ) : (
            <>
              <h1 className="auth-title">Join {preview.household_name}</h1>
              {err ? <p className="banner err">{err}</p> : null}
              <form onSubmit={submit}>
                <label className="block-label" htmlFor="email">
                  Your email
                </label>
                <input
                  id="email"
                  className="field"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                />
                <label className="block-label" htmlFor="password">
                  Choose a password
                </label>
                <input
                  id="password"
                  className="field"
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                />
                <p className="help">At least 8 characters.</p>
                <button type="submit" className="btn-primary block" disabled={busy}>
                  {busy ? "Joining…" : `Join ${preview.household_name}`}
                </button>
              </form>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
