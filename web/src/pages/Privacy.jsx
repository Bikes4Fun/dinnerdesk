import { go } from "../nav.js";

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
        <p>Dinnerdesk is a meal planner for a household. This is what we store, and what we do with it.</p>

        <h2>Your data</h2>
        <p>
          Get a copy of everything we store for your household: plans, grocery lists, pantry, filters, ratings,
          prep votes, Taste Lab answers and the recipes you added. Passwords and sign-in tokens are never included.
        </p>
        <p><a className="btn-secondary" href="/api/household/export" download>Download my data</a></p>

        <h2>Account</h2>
        <p>
          If you create an account we store your email (or the username you chose instead, plus a recovery email if you add one), whether and when you confirmed your email, a hash of
          your password (not the password), and your household name. A cookie named wp_session keeps you signed in for 30 days. You can sign out of this
          device, or every device, from Account &amp; security.
        </p>
        <p>
          Forgot-password emails are sent by Resend. We store a hash of the reset link, not the link. The link
          works once, for one hour. We answer the same way whether or not that email or username has an account (or a recovery email). You can change
          your email, swap it for a username, or add, change or remove a recovery email from Account &amp;
          security; a new email only takes over once you
          open the confirm link we send it.
        </p>
        <p>
          Confirm-email emails are also sent by Resend. While a confirm link is open we store the address it was
          sent to and a hash of the link, not the link. The link works once, for 24 hours.
        </p>
        <p>
          If you subscribe to the email newsletter, we store that choice with your household and may email you
          DinnerDesk Deals. Turn it off anytime at Settings → Email newsletter.
        </p>

        <h2>Your kitchen</h2>
        <p>
          Plans, grocery lists, pantry, recipe edits, favorites, hides, to-try marks, filters, and store or aisle
          choices are stored for your household in a database we host. Taste Lab stores the meals you like
          or pass, plus diet, allergy, and dislike choices. When you are signed in, those answers are tied to your
          account and used to suggest meals. Thumbs up or down on a planned meal, and on a prep step, are
          stored for your household and used to choose future meal suggestions. Prep step votes are kept so we
          can improve prep suggestions.
        </p>
        <p>
          Someone you invite joins that same household and can see and change it. Invite links expire after 7
          days. You can remove a member from Account &amp; security. Removing them ends their access.
        </p>

        <h2>Without an account</h2>
        <p>
          Guests use a private kitchen identified by a random device/browser cookie. All normal features work without an account. Reinstalling the app or clearing browser data can lose access to guest data. Create an account to protect it.
        </p>

        <h2>What we don’t collect</h2>
        <p>
          We don’t sell your data. We don’t take payment, location, or health data. Nutrition-tracker sync is not
          built. We don’t run ads or analytics.
        </p>
        <p>
          Recipe photos in the app are ones we have marked as ours to use. We don’t collect photos, reviews, or comments
          from cooks yet.
        </p>
        <p>The website loads fonts from Google Fonts. That request goes to Google.</p>

        <h2>Deleting data</h2>
        <p>
          Delete your account from Account & security after confirming your password. Your sign-ins, reset links and confirm links are removed. If other members remain, a household creator must transfer ownership before deleting their account. The last member’s deletion also removes their solo kitchen. The household creator or a designated household admin can separately delete a household: its kitchen and plans are removed, but members keep their accounts and receive empty solo households. Leaving or being removed from a household also preserves your account. Meal votes may be retained without account, household, browser, or session identifiers, grouped as individual history or household history.
        </p>

        <h2>Questions</h2>
        <p>
          See <a className="text-link" href="/support" onClick={(e) => { e.preventDefault(); go("/support"); }}>Help &amp; support</a> to contact us.
        </p>
      </div>
    </section>
    </div>
  );
}
