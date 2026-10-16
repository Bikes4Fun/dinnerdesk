import "./tip.css";

/** A tip: help text that explains a feature, shown with a purple sparkle star on a pale purple
 *  rounded card, right beside what it explains (docs/DESIGN.md).
 *  `id` becomes data-tip so scripts/list_tips.py can list every tip. */
export function Tip({ id, children, className = "" }) {
  return (
    <p className={`tip ${className}`.trim()} data-tip={id}>
      <Sparkle className="tip-star" />
      <span>{children}</span>
    </p>
  );
}

/** The sparkle star used by tips and the New meal plan button. */
export function Sparkle({ className = "", size = 16 }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M10 2.5c.4 4.3 2.7 6.6 7 7-4.3.4-6.6 2.7-7 7-.4-4.3-2.7-6.6-7-7 4.3-.4 6.6-2.7 7-7Z" />
      <path d="M18.5 13.5c.2 2.2 1.3 3.3 3.5 3.5-2.2.2-3.3 1.3-3.5 3.5-.2-2.2-1.3-3.3-3.5-3.5 2.2-.2 3.3-1.3 3.5-3.5Z" />
      <path d="M18.5 1.5c.15 1.5.9 2.25 2.4 2.4-1.5.15-2.25.9-2.4 2.4-.15-1.5-.9-2.25-2.4-2.4 1.5-.15 2.25-.9 2.4-2.4Z" />
    </svg>
  );
}
