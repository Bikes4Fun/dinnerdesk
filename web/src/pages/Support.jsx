import { useEffect, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";

/* Public help page (no sign-in), used as the App Store support URL. The contact address comes
   from the server's SUPPORT_EMAIL setting so it can change without a release. */
export function Support() {
  const [email, setEmail] = useState(null);

  useEffect(() => {
    api.support().then((r) => setEmail(r.email || "")).catch(() => setEmail(""));
  }, []);

  return (
    <div className="app">
    <section className="screen">
      <header className="top">
        <button type="button" className="icon-btn" onClick={() => (window.history.length > 1 ? window.history.back() : go("/"))} aria-label="Back">
          ←
        </button>
        <h1>Help &amp; support</h1>
      </header>
      <div className="scroll pad privacy">
        <p>Dinnerdesk plans a week of dinners for your household and builds the grocery list from it.</p>

        <h2>Contact us</h2>
        {email === null ? (
          <p className="muted">Loading…</p>
        ) : email ? (
          <p>
            Email <a className="text-link" href={`mailto:${email}?subject=Dinnerdesk%20help`}>{email}</a>. Tell us
            what you were doing, on iPhone or the website, and what you expected. A screenshot helps.
          </p>
        ) : (
          <p>Our support email isn’t set up yet. Please check back soon.</p>
        )}

        <h2>Common questions</h2>
        <p>
          <strong>I forgot my password.</strong> On the sign-in screen, tap “Forgot password?” We email a reset link
          that works once, for one hour.
        </p>
        <p>
          <strong>How do I share my plan?</strong> Settings → Account &amp; security → Invite someone to this
          household. Whoever opens the link and creates an account sees the same plan, recipes and grocery list.
        </p>
        <p>
          <strong>How do I delete my account?</strong> Settings → Account &amp; security → Delete account. If you are
          the last member, the household’s plans, pantry and grocery list are deleted too.
        </p>
        <p>
          <strong>A recipe or ingredient looks wrong.</strong> Email us the recipe name and what’s wrong, and we’ll
          fix it.
        </p>

        <h2>Privacy</h2>
        <p>
          See what we store and why on the <a className="text-link" href="/privacy" onClick={(e) => { e.preventDefault(); go("/privacy"); }}>privacy page</a>.
        </p>
      </div>
    </section>
    </div>
  );
}
