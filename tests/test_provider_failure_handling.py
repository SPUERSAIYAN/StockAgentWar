from __future__ import annotations

import unittest

from collectors.digital_oracle import (
    CMEFedWatchProvider,
    FedWatchUnavailable,
    PriceHistoryQuery,
    YahooPriceProvider,
)
from collectors.digital_oracle.http import HttpClientError
from collectors.digital_oracle.providers.base import ProviderParseError


class ProviderFailureHandlingTests(unittest.TestCase):
    def test_cme_blocked_access_returns_unavailable_status(self) -> None:
        result = CMEFedWatchProvider(http_client=BlockedCmeClient()).get_probabilities()

        self.assertIsInstance(result, FedWatchUnavailable)
        self.assertFalse(result.available)
        self.assertIn("blocked automated access", result.reason)

    def test_cme_missing_endpoint_returns_unavailable_status(self) -> None:
        result = CMEFedWatchProvider(http_client=MissingCmeClient()).get_probabilities()

        self.assertIsInstance(result, FedWatchUnavailable)
        self.assertFalse(result.available)
        self.assertIn("public JSON endpoint is unavailable", result.reason)

    def test_yahoo_empty_history_is_not_success(self) -> None:
        provider = YahooPriceProvider(fetcher=EmptyPriceFetcher())

        with self.assertRaisesRegex(ProviderParseError, "no usable d bars for SPY"):
            provider.get_history(PriceHistoryQuery(symbol="SPY", interval="d", limit=60))


class BlockedCmeClient:
    def get_json(self, url, *, params=None):
        raise HttpClientError(
            "request failed with HTTP 403: "
            "This IP address is blocked due to suspected web scraping activity"
        )


class MissingCmeClient:
    def get_json(self, url, *, params=None):
        raise HttpClientError(
            "request failed with HTTP 404: https://www.cmegroup.com/services/"
            "fed-funds-target/fed-funds-target.json"
        )


class EmptyPriceFetcher:
    def fetch_history(self, symbol: str, *, period: str, interval: str):
        return []


if __name__ == "__main__":
    unittest.main()
