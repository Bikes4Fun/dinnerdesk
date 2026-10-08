import { useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";

function friendlyError(e) {
  return (e && e.body && e.body.message) || (e && e.message) || "Something went wrong.";
}

export function Auth({ onAuthed }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [householdName, setHouseholdName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [sent, setSent] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (mode === "forgot") {
        await api.auth.forgotPassword({ email });
        setSent(true);
        return;
      }
      if (mode === "signup") {
        await api.auth.signup({
          email,
          password,
          household_name: householdName || "My household",
        });
      } else {
        await api.auth.login({ email, password });
      }
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
          <h1 className="auth-title">
            {mode === "signup" ? "Create your household" : mode === "forgot" ? "Reset your password" : "Welcome back"}
          </h1>

          {mode === "forgot" ? (
            <div>
              {err ? <p className="banner err">{err}</p> : null}
              {sent ? (
                <p className="banner ok">
                  If {email} has an account, a reset link is on its way. It works once, for 1 hour.
                </p>
              ) : (
                <form onSubmit={submit}>
                  <p className="help">Enter your email and we'll send you a link to set a new password.</p>
                  <label className="block-label" htmlFor="forgot_email">
                    Email
                  </label>
                  <input
                    id="forgot_email"
                    className="field"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                  />
                  <button type="submit" className="btn-primary block" disabled={busy}>
                    {busy ? "Sending…" : "Send reset link"}
                  </button>
                </form>
              )}
              <button
                type="button"
                className="text-link"
                onClick={() => {
                  setMode("login");
                  setSent(false);
                  setErr("");
                }}
              >
                Back to sign in
              </button>
            </div>
          ) : (
          <>
          <div className="auth-tabs">
            <button
              type="button"
              className={`tab-btn${mode === "login" ? " is-on" : ""}`}
              onClick={() => setMode("login")}
            >
              Sign in
            </button>
            <button
              type="button"
              className={`tab-btn${mode === "signup" ? " is-on" : ""}`}
              onClick={() => setMode("signup")}
            >
              Sign up
            </button>
          </div>

          {err ? <p className="banner err">{err}</p> : null}

          <form onSubmit={submit}>
            {mode === "signup" && (
              <>
                <label className="block-label" htmlFor="household_name">
                  Household name
                </label>
                <input
                  id="household_name"
                  className="field"
                  type="text"
                  placeholder="e.g. The Martins"
                  value={householdName}
                  onChange={(e) => setHouseholdName(e.target.value)}
                  autoComplete="organization"
                />
              </>
            )}

            <label className="block-label" htmlFor="email">
              Email
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
              Password
            </label>
            <input
              id="password"
              className="field"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
            />
            {mode === "signup" && <p className="help">At least 8 characters.</p>}
            {mode === "login" && (
              <button
                type="button"
                className="text-link"
                onClick={() => {
                  setMode("forgot");
                  setErr("");
                }}
              >
                Forgot password?
              </button>
            )}

            <button type="submit" className="btn-primary block" disabled={busy}>
              {busy ? "Please wait…" : mode === "signup" ? "Create household" : "Sign in"}
            </button>
            <button type="button" className="text-link" disabled={busy} onClick={() => go("/")}>
              Continue without an account
            </button>
            <button type="button" className="text-link" onClick={() => go("/privacy")}>
              Privacy
            </button>
          </form>
          </>
          )}
        </div>
      </section>
    </div>
  );
}
