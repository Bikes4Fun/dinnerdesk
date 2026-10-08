import { go } from "../nav.js";

export function TasteLab() {
  const search = new URLSearchParams(window.location.search);
  const frame = new URLSearchParams();
  frame.set("chrome", "app");
  if (search.get("swipe") === "1") frame.set("swipe", "1");
  const src = `/tastelab/?${frame.toString()}`;
  return (
    <section className="screen taste-lab-screen">
      <header className="top sub">
        <button
          type="button"
          className="icon-btn mob-back"
          aria-label="Back"
          onClick={() => {
            if (window.history.state) window.history.back();
            else go("/more");
          }}
        >
          ←
        </button>
        <h1>Taste Lab</h1>
        <span />
      </header>
      <iframe key={src} className="taste-frame" title="Taste Lab" src={src} />
    </section>
  );
}
