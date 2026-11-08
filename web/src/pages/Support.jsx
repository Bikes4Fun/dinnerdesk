import { useEffect, useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";

/* Public help page (no sign-in), used as the App Store support URL. The contact address comes
   from the server's SUPPORT_EMAIL setting so it can change without a release. */
export function Support() {
  const [email, setEmail] = useState(null);

  // The tour links to /support#ai; content renders after load, so scroll to it ourselves.
  useEffect(() => {
    const id = window.location.hash.slice(1);
    if (id) document.getElementById(id)?.scrollIntoView({ block: "start" });
  }, []);

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
        <p>
          Dinnerdesk plans a week of dinners for your household, builds the grocery list from those meals, and
          lists make-ahead prep. Taste Lab, under More, learns which meals you like so later suggestions fit.
        </p>

        <h2 id="ai">How we use AI</h2>
        <p>
          <strong>Are these recipes AI-generated? No.</strong> These are real recipes developed by people and
          shared publicly by reliable sources.
        </p>
        <p>
          <strong>AI photos and wording.</strong> We use AI to create representative photos and rewrite
          descriptions and instructions, rather than copy the source’s photos or exact wording.
        </p>
        <p>
          <strong>The photos are inspiration.</strong> AI images show the kind of dish, not the exact result you
          should expect. A recipe whose photo was made with AI says so on its page.
        </p>
        <p>
          <strong>Where the AI runs.</strong> Our AI images are made on a computer we own, not by an AI service in
          a data center.
        </p>
        <p>
          <strong>Reviewed by our team.</strong> Our team reviews the AI-generated photos and wording. We’re
          working through cooking the recipes, checking ingredients and steps, and replacing AI images with our own photos.
          A gold ★ marks recipes we’ve reviewed and tested. We’re also building a way for you to share your own
          photos of recipes you make.
        </p>

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
          <strong>How do I share my plan?</strong> Settings → Account &amp; security → Invite someone.
          Someone new opens the link and creates an account. Someone who already has an account pastes that same link into Join a household.
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
