import { useEffect, useState } from "react";
import { api } from "../api.js";

function friendlyError(e) {
  return (e && e.body && e.body.message) || (e && e.message) || "Something went wrong.";
}

export function AcceptInvite({ token, onAuthed }) {
  const [signedIn, setSignedIn] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewErr, setPreviewErr] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.auth.status().then((s) => setSignedIn(s.authenticated)).catch(() => {});
    api.previewInvite(token).then(setPreview).catch((e) => setPreviewErr(friendlyError(e)));
  }, [token]);

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (signedIn) {
        if (!confirm("Join this household? Your current solo kitchen will be removed; shared kitchens remain for their members.")) return;
        await api.joinHousehold(token);
      } else await api.acceptInvite({ token, email, password });
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
                {!signedIn && <>
                <label className="block-label" htmlFor="email">
                  Your email or a username
                </label>
                <input
                  id="email"
                  className="field"
                  type="text"
                  required
                  autoCapitalize="none"
                  spellCheck={false}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                />
                {email.trim() && !email.includes("@") && (
                  <p className="banner warn">No email means no password reset. If you forget your password, this account can't be recovered.</p>
                )}
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
                </>}
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
