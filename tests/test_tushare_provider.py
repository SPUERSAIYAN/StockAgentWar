from __future__ import annotations

import unittest

import pandas as pd

from collectors.tushare import (
    TushareProvider,
    TushareSettings,
    build_tushare_tasks,
    create_pro_api,
)


class TushareProviderTests(unittest.TestCase):
    def test_create_pro_api_sets_custom_http_url(self) -> None:
        fake_module = FakeTushareModule()

        pro = create_pro_api(
            TushareSettings(token="test-token", http_url="http://example.test/"),
            ts_module=fake_module,
        )

        self.assertEqual(fake_module.token, "test-token")
        self.assertEqual(pro._DataApi__http_url, "http://example.test/")

    def test_provider_parses_a_share_bars_and_daily_basic(self) -> None:
        api = FakeProApi()
        provider = TushareProvider(
            settings=TushareSettings(token="test-token"),
            api=api,
            ts_module=FakeTushareModule(),
        )

        history = provider.get_a_share_bars(ts_code="000001.SZ", limit=3)
        metrics = provider.get_daily_basic(ts_code="000001.SZ", limit=1)

        self.assertEqual(history.provider_id, "tushare")
        self.assertEqual(history.symbol, "000001.SZ")
        self.assertEqual([bar.date for bar in history.bars], ["2026-05-13", "2026-05-14", "2026-05-15"])
        self.assertEqual(history.latest.close, 11.0)
        self.assertEqual(metrics[0].ts_code, "000001.SZ")
        self.assertEqual(metrics[0].trade_date, "2026-05-15")
        self.assertEqual(metrics[0].total_market_cap_cny_100m, 2132.71)

    def test_task_builder_generates_tushare_market_tasks(self) -> None:
        tasks = build_tushare_tasks(
            symbols=["000001.SZ", "AAPL"],
            config={
                "price_history_limit": 90,
                "providers": {
                    "tushare": {
                        "enabled": True,
                        "token": "test-token",
                        "http_url": "http://example.test/",
                        "china_equity": True,
                        "us_equity": True,
                        "crypto": True,
                        "index_basic": True,
                        "index_daily": True,
                        "us_basic": True,
                        "us_daily": True,
                        "coincap": True,
                        "coincap_coins": ["BTC"],
                        "a_share_financials": True,
                        "moneyflow_lhb": True,
                        "index_etf": True,
                        "futures_options": True,
                        "macro_rates": True,
                    }
                },
            },
            is_a_share_symbol=lambda symbol: symbol.endswith((".SZ", ".SH", ".BJ")),
        )

        self.assertIn("equity.000001.SZ.tushare_price_daily", tasks)
        self.assertIn("equity.000001.SZ.tushare_daily_basic", tasks)
        self.assertIn("equity.AAPL.tushare_us_daily", tasks)
        self.assertIn("tushare.us_basic", tasks)
        self.assertIn("tushare.index_basic", tasks)
        self.assertIn("tushare.crypto.coincap.BTC", tasks)
        self.assertIn("equity.000001.SZ.tushare_fina_indicator", tasks)
        self.assertIn("equity.000001.SZ.tushare_moneyflow", tasks)
        self.assertIn("tushare.market.moneyflow_hsgt", tasks)
        self.assertIn("tushare.lhb.top_list", tasks)
        self.assertIn("tushare.index.000300.SH.weight", tasks)
        self.assertIn("tushare.fund.510300.SH.daily", tasks)
        self.assertIn("tushare.futures.basic", tasks)
        self.assertIn("tushare.options.basic", tasks)
        self.assertIn("tushare.macro.shibor", tasks)
        self.assertIn("tushare.macro.us_tycr", tasks)
        self.assertIn("tushare.macro.us_trycr", tasks)
        self.assertIn("tushare.macro.us_tbr", tasks)
        self.assertIn("tushare.macro.us_tltr", tasks)
        self.assertIn("tushare.macro.us_trltr", tasks)

    def test_provider_wraps_expanded_tables(self) -> None:
        provider = TushareProvider(
            settings=TushareSettings(token="test-token"),
            api=FakeProApi(),
            ts_module=FakeTushareModule(),
        )

        financials = provider.get_fina_indicator(ts_code="000001.SZ", period="20251231", limit=1)
        moneyflow = provider.get_moneyflow(ts_code="000001.SZ", limit=1)
        macro = provider.get_us_tycr(start_date="20240101", end_date="20240105", limit=1)

        self.assertEqual(financials.table, "fina_indicator")
        self.assertEqual(financials.rows[0]["ts_code"], "000001.SZ")
        self.assertEqual(moneyflow.table, "moneyflow")
        self.assertEqual(macro.table, "us_tycr")


class FakeProApi:
    def __getattr__(self, name: str):
        def method(**kwargs):
            row = {"table": name, **kwargs}
            if "ts_code" in kwargs:
                row["ts_code"] = kwargs["ts_code"]
            return pd.DataFrame([row])

        return method

    def stock_basic(self, **kwargs):
        return pd.DataFrame([])

    def index_basic(self, **kwargs):
        return pd.DataFrame([])

    def daily_basic(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260515",
                    "turnover_rate": 0.5,
                    "volume_ratio": 1.2,
                    "pe": 5.0,
                    "pb": 0.46,
                    "total_mv": 21327100.0,
                    "circ_mv": 21326760.0,
                }
            ]
        )

    def index_daily(self, **kwargs):
        return pd.DataFrame([])

    def us_basic(self, **kwargs):
        return pd.DataFrame([])

    def us_daily(self, **kwargs):
        return pd.DataFrame([])

    def coinlist(self, **kwargs):
        return pd.DataFrame([])

    def coincap(self, **kwargs):
        return pd.DataFrame([])

    def coin_bar(self, **kwargs):
        return pd.DataFrame([])


class FakeTushareModule:
    def __init__(self) -> None:
        self.token = ""

    def pro_api(self, token: str):
        self.token = token
        return FakeDataApi()

    def pro_bar(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260515",
                    "open": 10.5,
                    "high": 11.2,
                    "low": 10.4,
                    "close": 11.0,
                    "vol": 1000.0,
                },
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260514",
                    "open": 10.0,
                    "high": 10.8,
                    "low": 9.9,
                    "close": 10.5,
                    "vol": 900.0,
                },
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260513",
                    "open": 9.5,
                    "high": 10.1,
                    "low": 9.4,
                    "close": 10.0,
                    "vol": 800.0,
                },
            ]
        )


class FakeDataApi:
    pass


if __name__ == "__main__":
    unittest.main()
