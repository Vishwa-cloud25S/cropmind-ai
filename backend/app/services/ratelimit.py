"""In-memory fixed-window rate limiting (Phase 10 — FR/NFR hygiene, docs/04 §3.11).

Deliberately small and honest: per-process buckets keyed by (bucket, subject subject —
IP), sliding window of timestamps, O(window) memory per key. This is a
SINGLE-INSTANCE limiter (the MVP runs one API process); the interface is the
seam where a shared store (Redis-class) slots in for a multi-replica deploy —
the config numbers and the 429 contract stay identical.

429 responses are honest: they say what was limited, when to retry, and never
pretend the request succeeded partially.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.core.config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def retry_after(self, bucket: str, subject: str, per_minute: int) -> int | None:
        """Record the hit; return seconds-until-allowed (None if under the cap)."""
        now = time.monotonic()
        window_start = now - 60.0
        key = (bucket, subject)
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < window_start:
                hits.popleft()
            if len(hits) >= per_minute:
                return max(1, int(60.0 - (now - hits[0])))
            hits.append(now)
            # cheap global hygiene: forget idle keys when the map grows
            if len(self._hits) > 10000:
                for stale_key in [k for k, v in self._hits.items() if not v]:
                    del self._hits[stale_key]
            return None


_LIMITER: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    global _LIMITER
    if _LIMITER is None:
        _LIMITER = RateLimiter()
    return _LIMITER


def reset_limiter() -> None:
    global _LIMITER
    _LIMITER = None


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce(request: Request, bucket: str, per_minute: int) -> None:
    """Raise an honest 429 (Retry-After) when (bucket, caller IP) exceeds the cap."""
    if not get_settings().rate_limit_enabled:
        return
    seconds = get_limiter().retry_after(bucket, client_ip(request), per_minute)
    if seconds is not None:
        raise HTTPException(
            429,
            {
                "detail": f"rate limit exceeded for {bucket} — try again in {seconds}s "
                "(per-IP cap documented in docs/04 §3.11)",
                "bucket": bucket,
                "retry_after_s": seconds,
            },
            headers={"Retry-After": str(seconds)},
        )


def enforce_auth(request: Request) -> None:
    """Strict brake for credential endpoints (brute-force costing)."""
    enforce(request, "auth", get_settings().rate_limit_auth_per_minute)


def enforce_write(request: Request) -> None:
    """Generous per-IP cap for all other mutating calls."""
    enforce(request, "write", get_settings().rate_limit_write_per_minute)
