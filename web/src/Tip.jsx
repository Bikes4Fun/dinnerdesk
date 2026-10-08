import "./tip.css";

/** A tip: help text that explains a feature, shown with a purple ★ (docs/DESIGN.md).
 *  `id` becomes data-tip so scripts/list_tips.py can list every tip. */
export function Tip({ id, children, className = "" }) {
  return (
    <p className={`tip ${className}`.trim()} data-tip={id}>
      <span className="tip-star" aria-hidden="true">★</span>
      <span>{children}</span>
    </p>
  );
}
