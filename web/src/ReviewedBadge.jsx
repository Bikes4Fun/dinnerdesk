export function ReviewedBadge({ reviewed, className = "" }) {
  return reviewed ? <span className={`reviewed-badge ${className}`.trim()} aria-label="Reviewed by Dinnerdesk">✓ Reviewed</span> : null;
}
