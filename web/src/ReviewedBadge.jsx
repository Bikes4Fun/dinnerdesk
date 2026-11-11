export function ReviewedBadge({ reviewed }) {
  return reviewed ? <span className="reviewed-badge" aria-label="Reviewed by Dinnerdesk">✓ Reviewed</span> : null;
}
