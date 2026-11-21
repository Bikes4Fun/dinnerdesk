import { Component } from "react";
import { api } from "./api.js";
import { recordError } from "./trail.js";

/**
 * Catches a crash in the screens below it so the person gets an apology and a way out, and
 * the details go to the Inbox instead of onto their screen (#357). A React render error
 * unmounts the whole tree, so without this one bad screen is a blank page.
 *
 * The message and stack deliberately never render: they mean nothing to a cook, they can
 * carry internals, and they end up in screenshots. The Inbox gets them.
 */
export class ErrorBoundary extends Component {
  state = { crashed: false };

  static getDerivedStateFromError() {
    return { crashed: true };
  }

  componentDidCatch(error, info) {
    const message = String(error?.message || error || "Unknown error");
    recordError(message);
    api.reportCrash({
      message,
      stack: String(error?.stack || info?.componentStack || "").slice(0, 4000),
      screen: window.location.pathname,
    });
  }

  render() {
    if (!this.state.crashed) return this.props.children;
    return <CrashNotice onRetry={() => this.setState({ crashed: false })} />;
  }
}

/** The apology. No message, no stack: see the note above. */
export function CrashNotice({ onRetry }) {
  return (
    <main role="alert" className="screen pad crash">
      <h1>Something went wrong</h1>
      <p>
        That screen stopped working. It wasn’t anything you did, and nothing you’ve saved is lost.
        We’ve been told about it.
      </p>
      <div className="crash-actions">
        {onRetry && (
          <button type="button" className="btn-primary" onClick={onRetry}>Try again</button>
        )}
        <button type="button" className="btn-secondary" onClick={() => window.location.assign("/")}>
          Go to this week
        </button>
      </div>
    </main>
  );
}
