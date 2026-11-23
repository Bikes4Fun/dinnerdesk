import { go } from "../nav.js";
import { Copy } from "../Copy.js";

function Link({ href, children, extra, onClick, className }) {
  return (
    <button
      type="button"
      className={["list-link", className].filter(Boolean).join(" ")}
      onClick={onClick || (() => go(href))}
    >
      {children}
      {extra ? <em>{extra}</em> : null}
    </button>
  );
}

/** Matches iOS More: Kitchen, Prep (when no Prep tab), Taste Lab, Account, Feedback, Settings. */
export function More() {
  return (
    <section className="screen">
      <header className="top">
        <h1>More</h1>
      </header>
      <div className="scroll pad">
        <Link href="/kitchen">My kitchen</Link>
        {/* Shown only when the Prep tab is hidden (narrow screens). */}
        <Link href="/prep" className="more-prep-when-no-tab">{Copy.text("tour.how.4.title")}</Link>
        <Link href="/settings/tastelab">{Copy.text("tour.how.6.title")}</Link>
        <Link href="/settings/account">Account &amp; security</Link>
        <Link href="/settings/feedback">{Copy.text("ui.report.a.bug.or.suggest")}</Link>
        <Link href="/settings">Settings</Link>
      </div>
    </section>
  );
}
