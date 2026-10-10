import React, { useState } from "react";
import { photoSrc } from "./api.js";

/** Shared square frame for every recipe and ingredient photo, including placeholders. */
export default function FoodPhoto({ path, alt = "", className = "", hideUnavailable = false }) {
  const [failedPath, setFailedPath] = useState(null);
  const available = path && failedPath !== path;
  if (!available && hideUnavailable) return null;
  return (
    <span className={`food-photo ${className}`} style={{ aspectRatio: "1 / 1", height: "auto" }}>
      {available ? <img src={photoSrc(path)} alt={alt} onError={() => setFailedPath(path)} /> : <span className="food-photo-placeholder" aria-label={alt || undefined} />}
    </span>
  );
}
