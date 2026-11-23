import { Copy } from "./Copy.js";

/** "Your household can see all of it, including your allergies, likes, dislikes and Taste Lab history." */
export function HouseholdSharingNote() {
  return (
    <p className="privacy-note">
      <strong>{Copy.text("privacy.household.lead")}</strong> {Copy.text("privacy.household")}
    </p>
  );
}

/** The one-screen version for first open (sign up uses privacy.signup.note) (privacy.short.* in copy.json). */
function ShortSummary() {
  return (
    <div className="privacy-summary is-compact">
      <p className="privacy-promise">{Copy.text("privacy.short.sell")}</p>
      <h2>{Copy.text("privacy.short.keep.title")}</h2>
      <ul className="privacy-bullets">
        <li>{Copy.text("privacy.short.keep.1")}</li>
        <li>{Copy.text("privacy.short.keep.2")}</li>
        <li>
          {Copy.text("privacy.short.keep.3")} <span className="muted">{Copy.text("privacy.short.keep.3.note")}</span>
        </li>
        <li>{Copy.text("privacy.short.keep.4")}</li>
      </ul>
      <HouseholdSharingNote />
      <h2>{Copy.text("privacy.short.never.title")}</h2>
      <p className="privacy-never-line">{Copy.text("privacy.short.never")}</p>
    </div>
  );
}

/**
 * The short version of the privacy policy: what we keep, what we never collect, who else can see it.
 * Full at the top of Privacy; `compact` is the one-screen version for first open (sign up uses privacy.signup.note). Words:
 * privacy.* in copy.json, shared with iOS (PrivacySummaryView) and Android (PrivacySummary).
 */
export function PrivacySummary({ compact = false }) {
  if (compact) return <ShortSummary />;
  const keep = Copy.steps("privacy.keep", 4);
  const shared = Copy.steps("privacy.shared", 3);
  const never = Copy.text("privacy.never").split(" · ");
  return (
    <div className="privacy-summary">
      <p className="privacy-promise">{Copy.text("privacy.sell")}</p>

      <h2>{Copy.text("privacy.keep.title")}</h2>
      <ul className="privacy-rows">
        {keep.map((row, i) => (
          <li key={`keep-${i}`}>
            <strong>{row.title}</strong>
            <span>{row.body}</span>
          </li>
        ))}
      </ul>
      <p className="help">{Copy.text("privacy.keep.use")}</p>

      <h2>{Copy.text("privacy.never.title")}</h2>
      <ul className="privacy-never">
        {never.map((item) => <li key={item}>{item}</li>)}
      </ul>
      <p className="privacy-note">{Copy.text("privacy.health")}</p>

      <h2>{Copy.text("privacy.shared.title")}</h2>
      <ul className="privacy-rows">
        {shared.map((row, i) => (
          <li key={`shared-${i}`}>
            <strong>{row.title}</strong>
            <span>{row.body}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
