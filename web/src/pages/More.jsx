import { go } from "../nav.js";

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
        <Link href="/prep" className="more-prep-when-no-tab">Weekend prep</Link>
        <Link href="/settings/tastelab">Taste Lab</Link>
        <Link href="/settings/account">Account &amp; security</Link>
        <Link href="/settings/feedback">Report a bug or suggest a feature</Link>
        <Link href="/settings">Settings</Link>
      </div>
    </section>
  );
}
