"""A small in-process sliding-window rate limiter keyed by client address.

This protects expensive endpoints on a single instance. Deployments with several replicas
should enforce limits at the proxy or with a shared store instead.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request

from .errors import RateLimitedError

WINDOW_SECONDS = 60.0


class RateLimiter:
    def __init__(self, limit_per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit_per_minute
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= WINDOW_SECONDS:
                hits.popleft()
            if len(hits) >= self.limit:
                raise RateLimitedError(retry_after=max(1, math.ceil(WINDOW_SECONDS - (now - hits[0]))))
            hits.append(now)
            if len(self._hits) > 10_000:
                self._evict(now)

    def _evict(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] >= WINDOW_SECONDS]:
            del self._hits[key]

    def dependency(self, request: Request) -> None:
        self.check(request.client.host if request.client else "unknown")
