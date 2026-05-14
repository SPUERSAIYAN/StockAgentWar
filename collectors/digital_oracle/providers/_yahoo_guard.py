from __future__ import annotations

import os
import random
import threading
import time
from typing import Callable, TypeVar


T = TypeVar("T")
_YAHOO_LOCK = threading.Lock()
_LAST_YAHOO_REQUEST_AT = 0.0


def guarded_yahoo_request(request: Callable[[], T]) -> T:
    attempts = max(int(os.getenv("YAHOO_MAX_RETRIES", "3")), 1)
    retry_delay = max(float(os.getenv("YAHOO_RETRY_DELAY_SECONDS", "20")), 0.0)

    for attempt in range(1, attempts + 1):
        try:
            return run_throttled_yahoo_request(request)
        except Exception as exc:
            if attempt >= attempts or not is_yahoo_rate_limit(exc):
                raise
            jitter = random.uniform(0.0, min(2.0, retry_delay * 0.1))
            time.sleep((retry_delay * attempt) + jitter)

    raise RuntimeError("unreachable Yahoo retry state")


def run_throttled_yahoo_request(request: Callable[[], T]) -> T:
    global _LAST_YAHOO_REQUEST_AT
    with _YAHOO_LOCK:
        wait_for_yahoo_slot()
        try:
            return request()
        finally:
            _LAST_YAHOO_REQUEST_AT = time.monotonic()


def throttle_yahoo_request() -> None:
    global _LAST_YAHOO_REQUEST_AT
    with _YAHOO_LOCK:
        wait_for_yahoo_slot()
        _LAST_YAHOO_REQUEST_AT = time.monotonic()


def wait_for_yahoo_slot() -> None:
    min_interval = max(float(os.getenv("YAHOO_MIN_INTERVAL_SECONDS", "2.5")), 0.0)
    if min_interval <= 0:
        return

    now = time.monotonic()
    wait_seconds = min_interval - (now - _LAST_YAHOO_REQUEST_AT)
    if wait_seconds > 0:
        time.sleep(wait_seconds)


def is_yahoo_rate_limit(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return (
        "yfratelimiterror" in text
        or "too many requests" in text
        or "rate limited" in text
        or "429" in text
    )
