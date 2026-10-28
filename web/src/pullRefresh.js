import { useEffect, useState } from "react";

// Pull down from the top of a list to reload, like the iPhone's pull to refresh. Touch only.
// Returns how far the finger has pulled (0 when not pulling), for the hint at the top.
export const PULL_DISTANCE = 80;

export function usePullToRefresh() {
  const [pull, setPull] = useState(0);
  useEffect(() => {
    let startY = null;
    let distance = 0;
    const down = (e) => {
      const list = e.target.closest?.(".scroll");
      const busy = e.target.closest?.("input, textarea, select, .sheet-backdrop, .action-sheet");
      startY = list && !busy && list.scrollTop <= 0 && e.touches.length === 1 ? e.touches[0].clientY : null;
      distance = 0;
    };
    const move = (e) => {
      if (startY == null) return;
      distance = Math.max(0, e.touches[0].clientY - startY);
      setPull(Math.min(distance, PULL_DISTANCE * 1.5));
    };
    const up = () => {
      if (startY != null && distance >= PULL_DISTANCE) window.location.reload();
      startY = null;
      distance = 0;
      setPull(0);
    };
    window.addEventListener("touchstart", down, { passive: true });
    window.addEventListener("touchmove", move, { passive: true });
    window.addEventListener("touchend", up);
    window.addEventListener("touchcancel", up);
    return () => {
      window.removeEventListener("touchstart", down);
      window.removeEventListener("touchmove", move);
      window.removeEventListener("touchend", up);
      window.removeEventListener("touchcancel", up);
    };
  }, []);
  return pull;
}
