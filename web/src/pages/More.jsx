import { go } from "../nav.js";

function Link({ href, children, extra, onClick }) {
  return (
    <button type="button" className="list-link" onClick={onClick || (() => go(href))}>
      {children}
      {extra ? <em>{extra}</em> : null}
    </button>
  );
}

export function More() {
  return (
    <section className="screen">
      <header className="top">
        <h1>More</h1>
      </header>
      <div className="scroll pad">
        <Link href="/kitchen">My kitchen</Link>
        <Link href="/prep">Prep</Link>
        <Link href="/settings/tastelab">Taste Lab</Link>
        <Link href="/recipes?list=hidden">Hidden recipes</Link>
        <Link href="/settings">Settings</Link>
        <a className="list-link" href="https://x.com/DinnerDesk" target="_blank" rel="noopener noreferrer">
          Twitter
          <em>@DinnerDesk</em>
        </a>
        <Link onClick={() => window.dispatchEvent(new Event("dinnerdesk-tour"))}>Quick start tour</Link>
      </div>
    </section>
  );
}
