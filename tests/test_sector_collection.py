from __future__ import annotations

import unittest

from agents.information_agent import build_structured_information_context
from collectors import digital_oracle_collector
from collectors.connectors.china import build_china_equity_tasks


class SectorCollectionTests(unittest.TestCase):
    def test_china_tasks_do_not_include_board_sources(self) -> None:
        tasks = build_china_equity_tasks(
            symbols=[],
            config={
                "providers": {
                    "china_equity": {
                        "enabled": True,
                        "tencent": False,
                        "mootdx": False,
                    }
                }
            },
        )

        self.assertEqual(tasks, {})

    def test_requested_sector_does_not_generate_constituent_candidates(self) -> None:
        result = digital_oracle_collector.discover_candidate_universe(
            {"task": "分析半导体板块", "scan_scope": {"sectors": ["半导体"]}},
            {
                "providers": {"china_equity": {"enabled": True}},
                "candidate_discovery": {"enabled": True, "max_candidates": 15},
            },
        )

        self.assertEqual(result["mode"], "provider_sector_discovery")
        self.assertEqual(result["method"], "sector_constituent_source_unavailable")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["requested_sectors"], ["半导体"])
        self.assertIn("candidate_discovery.board_membership", result["errors"])

    def test_structured_context_has_no_board_member_field(self) -> None:
        output = build_structured_information_context(
            {
                "candidates": [
                    {
                        "symbol": "688981.SH",
                        "name": "中芯国际",
                        "metadata": {"sector": "半导体"},
                    }
                ]
            },
            {
                "collection_status": "ok",
                "source_count": 1,
                "error_count": 0,
                "sources": {
                    "equity.688981.SH.tencent_metrics": {
                        "items": [
                            {
                                "symbol": "688981.SH",
                                "price": 88.0,
                                "pe": 45.0,
                                "turnover_rate": 2.5,
                            }
                        ]
                    },
                },
                "errors": {},
            },
        )

        self.assertNotIn("sector_" + "constituents", output)
        self.assertEqual(output["sector_summary"][0]["sector_name"], "半导体")

    def test_sector_gap_is_reported_without_board_source(self) -> None:
        output = build_structured_information_context(
            {"candidates": []},
            {
                "collection_status": "failed",
                "source_count": 0,
                "error_count": 1,
                "sources": {},
                "errors": {
                    "symbols": "No candidate symbols were provided.",
                },
                "candidate_discovery": {
                    "mode": "provider_sector_discovery",
                    "requested_sectors": ["半导体"],
                    "candidates": [],
                },
            },
        )

        self.assertTrue(
            any("当前未接入板块成分股数据源" in gap for gap in output["data_gaps"])
        )

    def test_collector_keeps_sector_gap_when_no_symbols(self) -> None:
        output = digital_oracle_collector.collect_market_information(
            {"task": "分析半导体板块", "scan_scope": {"sectors": ["半导体"]}},
            {
                "collector": {
                    "enabled": True,
                    "providers": {
                        "china_equity": {"enabled": True, "tencent": False, "mootdx": False},
                        "macro": {"enabled": False},
                        "prediction_markets": {"enabled": False},
                        "crypto": {"enabled": False},
                        "web_search": {"enabled": False},
                    },
                }
            },
        )

        self.assertEqual(output["collection_status"], "empty")
        self.assertEqual(output["sources"], {})
        self.assertEqual(
            output["candidate_discovery"]["method"],
            "sector_constituent_source_unavailable",
        )


if __name__ == "__main__":
    unittest.main()
