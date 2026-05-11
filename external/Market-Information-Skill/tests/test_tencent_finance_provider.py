from __future__ import annotations

import unittest
from typing import Mapping

from digital_oracle.providers import (
    TencentBoardQuery,
    TencentFinanceProvider,
    TencentStockMetricsQuery,
)
from digital_oracle.providers.base import ProviderParseError
from digital_oracle.providers.tencent_finance import (
    TENCENT_FINANCE_QUOTE_URL,
    TENCENT_STOCK_APP_URL,
)


SAMPLE_PAYLOAD = (
    'v_sh600519="1~贵州茅台~600519~1370.07~1372.99~1372.89~11860~6377~5473~'
    '1370.05~6~1370.00~13~1369.96~1~1369.90~1~1369.79~2~1370.07~3~'
    '1370.08~2~1370.09~1~1370.10~4~1370.20~1~~20260511113000~-2.92~-0.21~'
    '1378.00~1366.00~1370.07/11860/1623900000~11860~162390.00~0.09~23.20~~'
    '1378.00~1366.00~0.87~16200.50~21000.80~8.60~1510.29~1235.69~1.93";\n'
    'v_hk00700="100~腾讯控股~00700~467.200~471.400~465.000~6934291.0~0~0~'
    '467.200~0~0~0~0~0~0~0~0~0~467.200~0~0~0~0~0~0~0~0~0~6934291.0~'
    '2026/05/11 10:03:53~-4.200~-0.89~471.200~465.000~467.200~6934291.0~'
    '3244672708.200~0~17.11~~0~0~1.32~42599.2569~42599.2569~TENCENT~'
    '0.97~683.000~460.200~2.35~27.78";\n'
    'v_sz300750="51~宁德时代~300750~250.00~249.00~249.50~1000~500~500~'
    '250.00~10~249.99~8~249.98~7~249.97~6~249.96~5~250.01~9~250.02~8~'
    '250.03~7~250.04~6~250.05~5~~20260511113001~1.00~0.40~252.00~248.00~'
    '250.00/1000/25000000~1000~2500.00~1.20~30.50~~252.00~248.00~1.61~'
    '7500.00~10000.00~5.10~273.90~224.10";'
)


class FakeTextClient:
    def __init__(self, payload: str = SAMPLE_PAYLOAD) -> None:
        self.payload = payload
        self.calls: list[tuple[str, Mapping[str, object] | None]] = []

    def get_text(self, url: str, *, params: Mapping[str, object] | None = None) -> str:
        self.calls.append((url, params))
        return self.payload


class TencentFinanceProviderTests(unittest.TestCase):
    def test_get_stock_metrics_parses_valuation_fields(self) -> None:
        client = FakeTextClient()
        provider = TencentFinanceProvider(http_client=client)

        metrics = provider.get_stock_metrics(("600519.SH", "sz300750"))

        self.assertEqual(len(metrics), 3)
        self.assertEqual(metrics[0].symbol, "sh600519")
        self.assertEqual(metrics[0].code, "600519")
        self.assertEqual(metrics[0].name, "贵州茅台")
        self.assertEqual(metrics[0].market_kind, "a_share")
        self.assertAlmostEqual(metrics[0].price or 0, 1370.07)
        self.assertAlmostEqual(metrics[0].turnover_rate or 0, 0.09)
        self.assertAlmostEqual(metrics[0].pe or 0, 23.20)
        self.assertAlmostEqual(metrics[0].pb or 0, 8.60)
        self.assertAlmostEqual(metrics[0].float_market_cap_cny_100m or 0, 16200.50)
        self.assertAlmostEqual(metrics[0].total_market_cap_cny_100m or 0, 21000.80)
        self.assertAlmostEqual(metrics[0].volume_ratio or 0, 1.93)
        self.assertEqual(metrics[0].timestamp, "2026-05-11 11:30:00")

    def test_normalizes_symbols_in_request_url(self) -> None:
        client = FakeTextClient()
        provider = TencentFinanceProvider(http_client=client)

        provider.get_stock_metrics(
            TencentStockMetricsQuery(
                symbols=("600519", "000001.SZ", "430047.BJ", "00700.HK", "AAPL.US")
            )
        )

        url, params = client.calls[0]
        self.assertEqual(url, f"{TENCENT_FINANCE_QUOTE_URL}sh600519,sz000001,bj430047,hk00700,usAAPL")
        self.assertIsNone(params)

    def test_accepts_single_string_symbol(self) -> None:
        client = FakeTextClient()
        provider = TencentFinanceProvider(http_client=client)

        metrics = provider.get_stock_metrics("300750")

        self.assertEqual(metrics[0].symbol, "sh600519")
        self.assertIn("sz300750", client.calls[0][0])

    def test_hk_us_and_index_helpers_delegate_to_quote_endpoint(self) -> None:
        client = FakeTextClient()
        provider = TencentFinanceProvider(http_client=client)

        hk = provider.get_hk_metrics("00700.HK")
        provider.get_us_metrics("AAPL.US")
        provider.get_index_metrics(("sh000001", "399006.SZ"))

        self.assertEqual(hk[1].market_kind, "hk")
        self.assertIn("hk00700", client.calls[0][0])
        self.assertIn("usAAPL", client.calls[1][0])
        self.assertIn("sh000001,sz399006", client.calls[2][0])

    def test_fetch_board_raw_builds_stock_app_url(self) -> None:
        client = FakeTextClient('{"code":0,"data":[]}')
        provider = TencentFinanceProvider(http_client=client)

        payload = provider.fetch_board_json_like(
            TencentBoardQuery(path="rank/sector", params={"type": "industry", "page": 1})
        )

        self.assertEqual(payload["code"], 0)
        url, _ = client.calls[0]
        self.assertTrue(url.startswith(f"{TENCENT_STOCK_APP_URL}/rank/sector?"))
        self.assertIn("type=industry", url)

    def test_rejects_unexpected_line_format(self) -> None:
        provider = TencentFinanceProvider(http_client=FakeTextClient("not a quote"))

        with self.assertRaises(ProviderParseError):
            provider.get_stock_metrics("600519")

    def test_describe(self) -> None:
        provider = TencentFinanceProvider(http_client=FakeTextClient())
        meta = provider.describe()

        self.assertEqual(meta.provider_id, "tencent_finance")
        self.assertIn("a_share_valuation", meta.capabilities)


if __name__ == "__main__":
    unittest.main()
