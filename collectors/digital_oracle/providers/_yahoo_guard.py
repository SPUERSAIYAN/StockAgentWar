from __future__ import annotations

import os
import threading
import time
from typing import Callable, TypeVar


T = TypeVar("T")
_YAHOO_LOCK = threading.Lock()
_LAST_YAHOO_REQUEST_AT = 0.0


def guarded_yahoo_request(request: Callable[[], T]) -> T:
    attempts = max(int(os.getenv("YAHOO_MAX_RETRIES", "2")), 1)
    retry_delay = max(float(os.getenv("YAHOO_RETRY_DELAY_SECONDS", "20")), 0.0)

    for attempt in range(1, attempts + 1):
        throttle_yahoo_request()
        try:
            return request()
        except Exception as exc:
            if attempt >= attempts or not is_yahoo_rate_limit(exc):
                raise
            time.sleep(retry_delay * attempt)

    raise RuntimeError("unreachable Yahoo retry state")


def throttle_yahoo_request() -> None:
    min_interval = max(float(os.getenv("YAHOO_MIN_INTERVAL_SECONDS", "1.0")), 0.0)
    if min_interval <= 0:
        return

    global _LAST_YAHOO_REQUEST_AT
    with _YAHOO_LOCK:
        now = time.monotonic()
        wait_seconds = min_interval - (now - _LAST_YAHOO_REQUEST_AT)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        _LAST_YAHOO_REQUEST_AT = time.monotonic()


def is_yahoo_rate_limit(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return (
        "yfratelimiterror" in text
        or "too many requests" in text
        or "rate limited" in text
        or "429" in text
    )
