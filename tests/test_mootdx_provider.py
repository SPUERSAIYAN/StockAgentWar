from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from collectors.digital_oracle.providers.mootdx_provider import _MootdxClientFactory


class MootdxProviderTests(unittest.TestCase):
    def test_client_factory_passes_fixed_server_to_mootdx(self) -> None:
        fake_quotes = FakeQuotes()

        with patch(
            "collectors.digital_oracle.providers.mootdx_provider.importlib.import_module",
            return_value=SimpleNamespace(Quotes=fake_quotes),
        ):
            factory = _MootdxClientFactory(
                server=("110.41.147.114", 7709),
                timeout=7,
                heartbeat=False,
            )

        self.assertEqual(factory.client(), "fake-client")
        self.assertEqual(fake_quotes.kwargs["server"], ("110.41.147.114", 7709))
        self.assertEqual(fake_quotes.kwargs["timeout"], 7)
        self.assertFalse(fake_quotes.kwargs["heartbeat"])


class FakeQuotes:
    def __init__(self) -> None:
        self.kwargs = {}

    def factory(self, **kwargs):
        self.kwargs = kwargs
        return "fake-client"


if __name__ == "__main__":
    unittest.main()
