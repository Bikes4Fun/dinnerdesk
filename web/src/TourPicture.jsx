import "./tour-picture.css";

/** A small drawn picture of the screen a quick-start card describes (#25). Drawn, not a
 *  screenshot, so it never goes stale. Decorative: the card's text says the same thing.
 *  Mirrors ios/dinnerdesk/TourScreenPicture.swift. `index` follows tour.how.N (0-based). */
export function TourPicture({ index }) {
  return (
    <div className="tour-pic" aria-hidden="true">
      {index === 0 && <Suggestions />}
      {index === 1 && <ThisPlan />}
      {index === 2 && <Grocery />}
      {index >= 3 && <Prep />}
    </div>
  );
}

const Bar = ({ w, dark = false }) => <span className={`tp-bar${dark ? " dark" : ""}`} style={{ width: `${w}%` }} />;

function Suggestions() {
  const tiles = ["coral", "plum", "warm", "coral"];
  const names = [80, 60, 70, 50];
  return <>
    <span className="tp-label">Suggested for you</span>
    <div className="tp-grid">
      {tiles.map((t, i) => <div key={i} className="tp-tile"><span className={`tp-photo ${t}`} /><Bar w={names[i]} dark /></div>)}
    </div>
    <div className="tp-pills"><span className="tp-pill">Swap</span><span className="tp-pill solid">Approve plan</span></div>
  </>;
}

function ThisPlan() {
  const rows = [["coral", 75, "Mon"], ["plum", 55, "Schedule"], ["warm", 65, "Schedule"]];
  return <>
    <span className="tp-label">This week</span>
    {rows.map(([t, w, day], i) => <div key={i} className="tp-row">
      <span className={`tp-photo small ${t}`} />
      <span className="tp-lines"><Bar w={w} dark /><Bar w={30} /></span>
      <span className="tp-chip">{day}</span>
    </div>)}
  </>;
}

function Check({ on }) {
  return <span className={`tp-check${on ? " on" : ""}`}>{on ? "✓" : ""}</span>;
}

function Grocery() {
  const row = (on, w, k) => <div key={k} className={`tp-row${on ? " done" : ""}`}><Check on={on} /><span className="tp-lines"><Bar w={w} dark={!on} /></span><span className="tp-qty" /></div>;
  return <>
    <span className="tp-label">Produce</span>
    {[row(false, 50, 1), row(false, 35, 2), row(true, 45, 3)]}
    <span className="tp-label">Pantry</span>
    {row(true, 40, 4)}
  </>;
}

function Prep() {
  const row = (on, w, k) => <div key={k} className={`tp-row${on ? " done" : ""}`}><Check on={on} /><span className="tp-lines"><Bar w={w} dark={!on} /></span></div>;
  return <>
    <span className="tp-label">Chop &amp; slice</span>
    {[row(true, 40, 1), row(false, 55, 2), row(false, 35, 3)]}
    <span className="tp-label">Sauces</span>
    {row(false, 60, 4)}
  </>;
}
