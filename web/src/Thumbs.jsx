import { Icon } from "./icons.jsx";

/** Thumbs up / down. rating is 1, -1 or 0; tapping the lit thumb again clears it. */
export function Thumbs({ rating = 0, subject, onRate, size = 18 }) {
  const thumb = (value, name, label) => {
    const on = rating === value;
    return (
      <button
        type="button"
        className={`thumb${on ? (value > 0 ? " is-up" : " is-down") : ""}`}
        aria-pressed={on}
        aria-label={`${label} ${subject}`}
        onClick={() => onRate(on ? 0 : value)}
      >
        <Icon name={name} size={size} />
      </button>
    );
  };
  return (
    <span className="thumbs">
      {thumb(1, "thumbs-up", "Like")}
      {thumb(-1, "thumbs-down", "Dislike")}
    </span>
  );
}
