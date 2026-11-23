import { Copy } from "./Copy.js";

/**
 * The short version of the privacy policy: what we keep, what we never collect, who else can see it.
 * Shown at the top of Privacy and on the first-open agreement screen. Words: privacy.* in copy.json,
 * shared with iOS (PrivacySummaryView) and Android (PrivacySummary).
 */
export function PrivacySummary({ compact = false }) {
  const keep = Copy.steps("privacy.keep", 4);
  const shared = Copy.steps("privacy.shared", 3);
  const never = Copy.text("privacy.never").split(" · ");
  return (
    <div className={`privacy-summary${compact ? " is-compact" : ""}`}>
      <p className="privacy-promise">{Copy.text("privacy.sell")}</p>

      <h2>{Copy.text("privacy.keep.title")}</h2>
      <ul className="privacy-rows">
        {keep.map((row) => (
          <li key={row.title}>
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

      {!compact && (
        <>
          <h2>{Copy.text("privacy.shared.title")}</h2>
          <ul className="privacy-rows">
            {shared.map((row) => (
              <li key={row.title}>
                <strong>{row.title}</strong>
                <span>{row.body}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
