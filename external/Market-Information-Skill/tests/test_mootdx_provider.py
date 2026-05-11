from __future__ import annotations

import unittest

from digital_oracle.providers import (
    MootdxBarQuery,
    MootdxCompanyProfileQuery,
    MootdxDateRangeQuery,
    MootdxIntradayQuery,
    MootdxTransactionQuery,
    MootdxProvider,
)


class FakeMootdxClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def bars(self, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(("bars", kwargs))
        return [
            {
                "datetime": "2026-05-08 09:31:00",
                "open": 10.0,
                "high": 10.5,
                "low": 9.9,
                "close": 10.2,
                "vol": 12345,
            },
            {
                "datetime": "2026-05-08 09:32:00",
                "open": 10.2,
                "high": 10.8,
                "low": 10.1,
                "close": 10.6,
                "volume": 23456,
            },
        ]

    def index(self, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(("index", kwargs))
        return [
            {
                "year": 2026,
                "month": 5,
                "day": 8,
                "open": 3000.0,
                "high": 3010.0,
                "low": 2990.0,
                "close": 3005.0,
            }
        ]

    def quotes(self, symbol: object, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(("quotes", {"symbol": symbol, **kwargs}))
        return [
            {
                "code": "600519",
                "name": "贵州茅台",
                "price": 1370.07,
                "last_close": 1372.99,
                "open": 1372.89,
                "high": 1378.0,
                "low": 1366.0,
                "vol": 11860,
                "amount": 1623900000,
                "bid1": 1370.05,
                "bid_vol1": 6,
                "bid2": 1370.00,
                "bid_vol2": 13,
                "ask1": 1370.07,
                "ask_vol1": 3,
                "ask2": 1370.08,
                "ask_vol2": 2,
            }
        ]

    def minute(self, symbol: str, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(("minute", {"symbol": symbol, **kwargs}))
        return [{"time": "09:31", "price": 10.2, "avg_price": 10.1, "vol": 1200}]

    def minutes(self, symbol: str, date: str, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(("minutes", {"symbol": symbol, "date": date, **kwargs}))
        return [{"time": "09:32", "price": 10.4, "avg_price": 10.2, "volume": 1300}]

    def transaction(self, symbol: str, start: int = 0, offset: int = 800, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(("transaction", {"symbol": symbol, "start": start, "offset": offset, **kwargs}))
        return [{"time": "09:31:03", "price": 10.2, "vol": 100, "buyorsell": "B"}]

    def transactions(
        self,
        symbol: str,
        start: int = 0,
        offset: int = 800,
        date: str = "",
        **kwargs: object,
    ) -> list[dict[str, object]]:
        self.calls.append(("transactions", {"symbol": symbol, "start": start, "offset": offset, "date": date, **kwargs}))
        return [{"time": "09:32:03", "price": 10.3, "volume": 200, "direction": "S"}]

    def xdxr(self, symbol: str, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(("xdxr", {"symbol": symbol, **kwargs}))
        return [{"date": "2026-05-08", "category": "分红", "cash": 1.5}]

    def stocks(self, market: int, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(("stocks", {"market": market, **kwargs}))
        return [{"code": "600519", "name": "贵州茅台", "pre_close": 1372.99}]

    def stock_count(self, market: int) -> int:
        self.calls.append(("stock_count", {"market": market}))
        return 2260

    def k(self, symbol: str, begin: str, end: str, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(("k", {"symbol": symbol, "begin": begin, "end": end, **kwargs}))
        return [
            {
                "date": "2026-05-08",
                "open": 10.0,
                "high": 10.5,
                "low": 9.9,
                "close": 10.2,
                "volume": 12345,
            }
        ]

    def finance(self, symbol: str, **kwargs: object) -> dict[str, object]:
        self.calls.append(("finance", {"symbol": symbol, **kwargs}))
        return {
            "updated_date": 20260511,
            "ipo_date": 20010827,
            "jinglirun": 85000000000.0,
            "zhuyingshouru": 160000000000.0,
            "yingyelirun": 100000000000.0,
            "zongzichan": 300000000000.0,
            "jingzichan": 220000000000.0,
            "zongguben": 1256197800.0,
            "liutongguben": 1256197800.0,
            "meigujingzichan": 175.13,
            "gudongrenshu": 180000,
        }

    def F10(self, symbol: str, name: str = "") -> object:  # noqa: N802
        self.calls.append(("F10", {"symbol": symbol, "name": name}))
        if name == "公司概况":
            return "公司名称: 示例股份有限公司\n主营业务: 高端制造"
        if name == "最新提示":
            return "最新财报摘要: 营收增长"
        if not name:
            return {"公司概况": "概况全文", "财务分析": "财报摘要"}
        return ""

    def F10C(self, symbol: str) -> list[dict[str, object]]:  # noqa: N802
        self.calls.append(("F10C", {"symbol": symbol}))
        return [{"name": "公司概况"}, {"name": "财务分析"}]


class MootdxProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FakeMootdxClient()
        self.provider = MootdxProvider(client=self.client)

    def test_get_bars_maps_minute_frequency_and_symbol(self) -> None:
        history = self.provider.get_bars(
            MootdxBarQuery(symbol="600519.SH", frequency="1m", offset=2, adjust="qfq")
        )

        self.assertEqual(history.symbol, "600519")
        self.assertEqual(history.interval, "1m")
        self.assertEqual(history.provider_id, "mootdx")
        self.assertEqual(len(history.bars), 2)
        self.assertEqual(history.latest.close, 10.6)
        method, kwargs = self.client.calls[0]
        self.assertEqual(method, "bars")
        self.assertEqual(kwargs["symbol"], "600519")
        self.assertEqual(kwargs["frequency"], 8)
        self.assertEqual(kwargs["adjust"], "qfq")

    def test_get_index_bars_uses_index_method(self) -> None:
        history = self.provider.get_bars(
            MootdxBarQuery(symbol="sh000001", frequency="day", is_index=True, offset=1)
        )

        self.assertEqual(history.symbol, "000001")
        self.assertEqual(history.interval, "day")
        self.assertEqual(history.latest.date, "2026-05-08")
        self.assertEqual(self.client.calls[0][0], "index")

    def test_get_realtime_quotes(self) -> None:
        quotes = self.provider.get_realtime_quotes(["600519.SH"])

        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0].symbol, "600519")
        self.assertEqual(quotes[0].name, "贵州茅台")
        self.assertAlmostEqual(quotes[0].price or 0, 1370.07)
        self.assertEqual(self.client.calls[0][1]["symbol"], "600519")

    def test_get_order_books_from_quote_levels(self) -> None:
        books = self.provider.get_order_books("600519.SH")

        self.assertEqual(books[0].symbol, "600519")
        self.assertAlmostEqual(books[0].levels[0].bid_price or 0, 1370.05)
        self.assertEqual(books[0].levels[0].bid_volume, 6)
        self.assertAlmostEqual(books[0].levels[1].ask_price or 0, 1370.08)

    def test_get_intraday_points_current_and_historical(self) -> None:
        current = self.provider.get_intraday_points("600519.SH")
        historical = self.provider.get_intraday_points(
            MootdxIntradayQuery(symbol="600519.SH", date="20260508")
        )

        self.assertEqual(current[0].time, "09:31")
        self.assertAlmostEqual(historical[0].price or 0, 10.4)
        self.assertEqual(self.client.calls[0][0], "minute")
        self.assertEqual(self.client.calls[1][0], "minutes")

    def test_get_transactions_current_and_historical(self) -> None:
        current = self.provider.get_transactions(MootdxTransactionQuery(symbol="600519.SH", offset=10))
        historical = self.provider.get_transactions(
            MootdxTransactionQuery(symbol="600519.SH", date="20260508", offset=10)
        )

        self.assertEqual(current[0].direction, "B")
        self.assertEqual(historical[0].direction, "S")
        self.assertEqual(self.client.calls[0][0], "transaction")
        self.assertEqual(self.client.calls[1][0], "transactions")

    def test_get_ohlc_range(self) -> None:
        history = self.provider.get_ohlc_range(
            MootdxDateRangeQuery(symbol="600519.SH", begin="2026-05-01", end="2026-05-11", adjust="qfq")
        )

        self.assertEqual(history.interval, "day")
        self.assertEqual(history.latest.close, 10.2)
        self.assertEqual(self.client.calls[0][1]["adjust"], "qfq")

    def test_corporate_actions_and_stock_list(self) -> None:
        actions = self.provider.get_corporate_actions("600519.SH")
        stocks = self.provider.list_stocks("sh")
        count = self.provider.get_stock_count("sz")

        self.assertEqual(actions[0].category, "分红")
        self.assertEqual(stocks[0].symbol, "600519")
        self.assertEqual(count, 2260)
        self.assertEqual(self.client.calls[1][1]["market"], 1)
        self.assertEqual(self.client.calls[2][1]["market"], 0)

    def test_get_financial_summary_computes_eps(self) -> None:
        summary = self.provider.get_financial_summary("sh600519")

        self.assertEqual(summary.symbol, "600519")
        self.assertEqual(summary.updated_date, "20260511")
        self.assertAlmostEqual(summary.eps or 0, 67.6645, places=4)
        self.assertEqual(summary.eps_source, "net_profit/total_share_capital")
        self.assertAlmostEqual(summary.book_value_per_share or 0, 175.13)
        self.assertEqual(summary.shareholders, 180000)

    def test_get_shareholder_snapshot(self) -> None:
        snapshot = self.provider.get_shareholder_snapshot("sh600519")

        self.assertEqual(snapshot.symbol, "600519")
        self.assertEqual(snapshot.shareholders, 180000)
        self.assertAlmostEqual(snapshot.total_share_capital or 0, 1256197800.0)

    def test_get_company_profile_specific_sections(self) -> None:
        profile = self.provider.get_company_profile(
            MootdxCompanyProfileQuery(symbol="600519", sections=("公司概况", "最新提示"))
        )

        self.assertIn("公司概况", profile.sections)
        self.assertIn("高端制造", profile.overview or "")
        self.assertIn("最新提示", profile.sections)

    def test_get_company_profile_include_all(self) -> None:
        profile = self.provider.get_company_profile(
            MootdxCompanyProfileQuery(symbol="600519", include_all=True)
        )

        self.assertEqual(profile.sections["财务分析"], "财报摘要")

    def test_list_company_sections(self) -> None:
        sections = self.provider.list_company_sections("600519")

        self.assertEqual(sections, ("公司概况", "财务分析"))

    def test_describe(self) -> None:
        meta = self.provider.describe()

        self.assertEqual(meta.provider_id, "mootdx")
        self.assertIn("a_share_fundamentals", meta.capabilities)


if __name__ == "__main__":
    unittest.main()
