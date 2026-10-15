"""Request performance tracking: per-request DB query totals and named phase timings.

The HTTP middleware in app.main starts a RequestStats for each /api request. PgConnection
adds every query to it, and Laps.publish adds a code path's phases to it, so one log line
and the Server-Timing header show where a request spent its time.
"""

from __future__ import annotations

import contextvars
import time
from dataclasses import dataclass, field


@dataclass
class RequestStats:
    queries: int = 0
    db_ms: float = 0.0
    phases: dict[str, float] = field(default_factory=dict)


# Sync routes run on a worker thread with a copy of this context. The RequestStats object
# itself is shared, so what the route records is visible to the middleware afterwards.
_current: contextvars.ContextVar[RequestStats | None] = contextvars.ContextVar("request_stats", default=None)


def start_request() -> RequestStats:
    stats = RequestStats()
    _current.set(stats)
    return stats


def record_query(ms: float) -> None:
    stats = _current.get()
    if stats is not None:
        stats.queries += 1
        stats.db_ms += ms


class Laps:
    """Back-to-back phase timings: each lap(name) closes the phase that just ran.

    Phases can't overlap or leave gaps, so they always add up to the total. Counts are
    extra numbers worth logging next to the timings (candidates, filtered out, ...).
    """

    def __init__(self) -> None:
        self._t = time.perf_counter()
        self.ms: dict[str, float] = {}
        self.counts: dict[str, object] = {}

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.ms[name] = self.ms.get(name, 0.0) + (now - self._t) * 1000
        self._t = now

    def total(self) -> float:
        return sum(self.ms.values())

    def fmt(self) -> str:
        counts = " ".join(f"{k}={v}" for k, v in self.counts.items())
        times = " ".join(f"{k}={v:.1f}ms" for k, v in self.ms.items())
        return " ".join(part for part in (counts, times, f"total={self.total():.1f}ms") if part)

    def publish(self, prefix: str) -> None:
        """Add these phases to the current request's Server-Timing, as prefix.phase."""
        stats = _current.get()
        if stats is None:
            return
        for name, ms in self.ms.items():
            key = f"{prefix}.{name}"
            stats.phases[key] = stats.phases.get(key, 0.0) + ms


def server_timing(stats: RequestStats, total_ms: float) -> str:
    parts = [f"app;dur={total_ms:.1f}", f'db;dur={stats.db_ms:.1f};desc="{stats.queries} queries"']
    parts.extend(f"{name};dur={ms:.1f}" for name, ms in stats.phases.items())
    return ", ".join(parts)
