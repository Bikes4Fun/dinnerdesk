import { Copy } from "./Copy.js";

export function ReviewedBadge({ reviewed, className = "" }) {
  return reviewed ? <span className={`reviewed-badge ${className}`.trim()} aria-label={Copy.text("recipe.reviewed.description")}>✓ {Copy.text("recipe.reviewed")}</span> : null;
}
