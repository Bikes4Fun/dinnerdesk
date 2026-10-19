import { useEffect, useState } from "react";
import { api } from "../api.js";

/** Opened from the emailed link: /verify/<token>. */
export function VerifyEmail({ token, onDone }) {
  const [email, setEmail] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    api.auth
      .confirmEmail({ token })
      .then((r) => setEmail(r.email))
      .catch((e) => setErr((e && e.body && e.body.message) || (e && e.message) || "Something went wrong."));
  }, [token]);

  return (
    <div className="app is-auth">
      <section className="screen auth-screen">
        <div className="scroll pad auth-pad">
          <div className="brand auth-brand">Dinnerdesk</div>
          <h1 className="auth-title">Confirm email</h1>
          {err ? <p className="banner err">{err}</p> : null}
          {email ? <p className="banner ok">Confirmed. You sign in as {email} from now on.</p> : null}
          {!err && !email ? <p className="help">Confirming…</p> : null}
          <button type="button" className="btn-primary block" onClick={() => onDone()}>
            Continue
          </button>
        </div>
      </section>
    </div>
  );
}
