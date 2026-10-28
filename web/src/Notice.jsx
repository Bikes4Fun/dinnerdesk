import { Icon } from "./icons.jsx";

/** A one-line notice above the page (guest kitchen, email, What's new), closed with ×. */
export function Notice({ children, onDismiss }) {
  return (
    <div className="guest-notice">
      <span>{children}</span>
      <button type="button" aria-label="Dismiss" onClick={onDismiss}><Icon name="close" size={14} /></button>
    </div>
  );
}
