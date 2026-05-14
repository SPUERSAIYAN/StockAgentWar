from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from collectors.digital_oracle.providers import _yahoo_guard


class YahooGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        _yahoo_guard._LAST_YAHOO_REQUEST_AT = 0.0

    def test_default_throttle_waits_between_yahoo_requests(self) -> None:
        _yahoo_guard._LAST_YAHOO_REQUEST_AT = 100.0

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(_yahoo_guard.time, "monotonic", side_effect=[101.0, 102.5]),
            patch.object(_yahoo_guard.time, "sleep") as sleep,
        ):
            _yahoo_guard.throttle_yahoo_request()

        sleep.assert_called_once_with(1.5)
        self.assertEqual(_yahoo_guard._LAST_YAHOO_REQUEST_AT, 102.5)

    def test_guarded_request_retries_yahoo_rate_limits(self) -> None:
        calls = 0

        def request() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("YFRateLimitError: Too Many Requests")
            return "ok"

        with (
            patch.dict(
                os.environ,
                {
                    "YAHOO_MAX_RETRIES": "2",
                    "YAHOO_MIN_INTERVAL_SECONDS": "0",
                    "YAHOO_RETRY_DELAY_SECONDS": "0",
                },
            ),
            patch.object(_yahoo_guard.random, "uniform", return_value=0.0),
            patch.object(_yahoo_guard.time, "sleep") as sleep,
        ):
            result = _yahoo_guard.guarded_yahoo_request(request)

        self.assertEqual(result, "ok")
        self.assertEqual(calls, 2)
        sleep.assert_called_once_with(0.0)


if __name__ == "__main__":
    unittest.main()
