"""Rate limit service — per-API-key sliding window (PRD NFR: basic security).

In-memory on purpose: the platform targets a single server (PRD 5), and the check
must be fast. Each authenticated request (chat or data) counts against its key's
window; over the limit raises RateLimitError (429).
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock

from backend.core.config import get_settings
from backend.core.errors import RateLimitError
from backend.shared.constants import RATE_LIMIT_WINDOW_SECONDS

# ============== STATE ==============

_buckets: dict[int, deque[float]] = {}
_lock = Lock()


# ============== PUBLIC API ==============

def check_rate_limit(api_key_id: int) -> None:
    """Counts one request for the key and raises RateLimitError when over the per-minute limit."""
    limit_per_minute = get_settings().rate_limit_per_minute
    now = time.monotonic()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    with _lock:
        window = _buckets.setdefault(api_key_id, deque())
        while window and window[0] <= window_start:
            window.popleft()
        if len(window) >= limit_per_minute:
            raise RateLimitError(
                f"Rate limit exceeded: max {limit_per_minute} requests per minute for this API key."
            )
        window.append(now)
