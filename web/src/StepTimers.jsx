import { useEffect, useState } from "react";
import { clock, parseTimers } from "./timers.js";

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    osc.frequency.value = 880;
    osc.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.4);
  } catch {
    // No audio available; the on-screen message still shows.
  }
}

function StepTimer({ timer }) {
  const [endsAt, setEndsAt] = useState(null);
  const [now, setNow] = useState(Date.now());
  const left = endsAt ? (endsAt - now) / 1000 : timer.seconds;
  const done = endsAt && left <= 0;

  useEffect(() => {
    if (!endsAt || done) return undefined;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [endsAt, done]);

  useEffect(() => {
    if (!done) return;
    beep();
    if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
  }, [done]);

  if (!endsAt) {
    return (
      <button type="button" className="step-timer" onClick={() => { setNow(Date.now()); setEndsAt(Date.now() + timer.seconds * 1000); }}>
        ⏱ {timer.label}
      </button>
    );
  }
  return (
    <span className={`step-timer is-running${done ? " is-done" : ""}`} role="timer" aria-live={done ? "assertive" : "off"}>
      {done ? "Time's up" : clock(left)}
      <button type="button" className="text-link" onClick={() => setEndsAt(null)}>{done ? "Dismiss" : "Stop"}</button>
    </span>
  );
}

/** A start button for each time mentioned in a step. */
export function StepTimers({ text }) {
  const timers = parseTimers(text);
  if (!timers.length) return null;
  return (
    <div className="step-timers">
      {timers.map((t) => <StepTimer key={t.label} timer={t} />)}
    </div>
  );
}
