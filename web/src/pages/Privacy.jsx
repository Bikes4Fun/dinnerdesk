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

        <h2>Account</h2>
        <p>
          If you create an account we store your email, a hash of your password (not the password), and your
          household name. A cookie named wp_session keeps you signed in for 30 days. You can sign out of this
          device, or every device, from Account &amp; security.
        </p>
        <p>
          Forgot-password emails are sent by Resend. We store a hash of the reset link, not the link. The link
          works once, for one hour. We answer the same way whether or not that email has an account.
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
          If sign-in is not required, the app uses one shared guest household on the server. Anything added there
          is not private to you. Create an account for a household of your own.
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
          Delete your account any time from Account &amp; security. Your password is asked for first. If you are the
          last member, the household goes too: its plans, pantry, grocery list, ratings and the recipes you added. If
          others are still in the household, it stays for them. You can also remove other people from Account &amp;
          security.
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
