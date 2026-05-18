from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.sax.saxutils import escape

from agents.information_agent import build_structured_information_context
from collectors import digital_oracle_collector
from collectors.connectors.china import build_china_equity_tasks
from collectors.local_a_share_concepts import discover_local_concept_board_candidates


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

    def test_local_loader_matches_concepts_not_industry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = build_test_concept_workbook(Path(temp_dir) / "concepts.xlsx")
            result = discover_local_concept_board_candidates(
                ["半导体"],
                {
                    "local_concept_board_path": str(workbook_path),
                    "max_candidates": 10,
                    "a_share_filters": {"exclude_st": True, "min_market_cap_yi": 0, "max_pe": 100},
                },
            )

        symbols = [item["symbol"] for item in result["candidates"]]
        self.assertEqual(symbols, ["300001.SZ"])
        self.assertEqual(result["method"], "local_excel_concept_board")
        self.assertEqual(result["matched_sectors"][0]["match_type"], "contains")
        self.assertNotIn("600001.SH", symbols)

    def test_requested_sector_generates_local_constituent_candidates(self) -> None:
        result = digital_oracle_collector.discover_candidate_universe(
            {"task": "分析半导体板块", "scan_scope": {"sectors": ["半导体"]}},
            {
                "providers": {"china_equity": {"enabled": True}},
                "candidate_discovery": {"enabled": True, "max_candidates": 15},
            },
        )

        self.assertEqual(result["mode"], "provider_sector_discovery")
        self.assertEqual(result["method"], "local_excel_concept_board")
        self.assertTrue(result["candidates"])
        self.assertEqual(result["requested_sectors"], ["半导体"])
        self.assertGreater(result["matched_count"], 0)
        self.assertNotIn("candidate_discovery.board_membership", result["errors"])
        self.assertEqual(result["candidates"][0]["market"], "CN")
        self.assertIn("sector", result["candidates"][0]["metadata"])

    def test_question_understanding_sector_terms_are_fallback(self) -> None:
        result = digital_oracle_collector.discover_candidate_universe(
            {
                "task": "分析 A 股板块",
                "scan_scope": {"sectors": []},
                "question_understanding": {"sector_terms": ["半导体"]},
            },
            {
                "providers": {"china_equity": {"enabled": True}},
                "candidate_discovery": {"enabled": True, "max_candidates": 5},
            },
        )

        self.assertEqual(result["method"], "local_excel_concept_board")
        self.assertEqual(result["requested_sectors"], ["半导体"])
        self.assertTrue(result["candidates"])

    def test_data_collection_action_terms_are_sector_fallback(self) -> None:
        result = digital_oracle_collector.discover_candidate_universe(
            {
                "task": "分析 A 股板块",
                "scan_scope": {"sectors": []},
                "question_understanding": {"sector_terms": []},
                "data_collection_actions": [
                    {
                        "action": "CALL_LOCAL_CONCEPT_BOARD",
                        "provider_group": "china_equity",
                        "source": "astockdate/全部A股20264.xlsx",
                        "input_terms": ["半导体"],
                    }
                ],
            },
            {
                "providers": {"china_equity": {"enabled": True}},
                "candidate_discovery": {"enabled": True, "max_candidates": 5},
            },
        )

        self.assertEqual(result["method"], "local_excel_concept_board")
        self.assertEqual(result["requested_sectors"], ["半导体"])
        self.assertTrue(result["candidates"])

    def test_missing_local_concept_file_returns_gap_without_fabricating_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.xlsx"
            result = digital_oracle_collector.discover_candidate_universe(
                {"task": "分析半导体板块", "scan_scope": {"sectors": ["半导体"]}},
                {
                    "providers": {"china_equity": {"enabled": True}},
                    "candidate_discovery": {
                        "enabled": True,
                        "max_candidates": 15,
                        "local_concept_board_path": str(missing_path),
                    },
                },
            )

        self.assertEqual(result["method"], "local_excel_concept_board")
        self.assertEqual(result["candidates"], [])
        self.assertIn("candidate_discovery.local_concept_board", result["errors"])
        self.assertNotIn("candidate_discovery.board_membership", result["errors"])

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

    def test_sector_gap_is_reported_when_local_board_has_no_candidates(self) -> None:
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
            any("本地概念板块表未形成可用候选" in gap for gap in output["data_gaps"])
        )

    def test_collector_keeps_local_concept_source_when_market_tasks_disabled(self) -> None:
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

        self.assertIn(output["collection_status"], {"ok", "partial"})
        self.assertIn("candidate_discovery.local_concept_board", output["sources"])
        self.assertEqual(
            output["candidate_discovery"]["method"],
            "local_excel_concept_board",
        )

    def test_sector_profile_covers_more_candidates_with_shallow_stock_tasks(self) -> None:
        config, profile = digital_oracle_collector.apply_a_share_collection_profile(
            {
                "task": "分析半导体板块",
                "scan_scope": {"sectors": ["半导体"]},
                "metadata": {"ui_mode": "a_share_sector"},
            },
            full_depth_collector_config(),
        )

        self.assertEqual(profile, "sector_shallow")
        self.assertEqual(config["candidate_discovery"]["max_candidates"], 60)
        self.assertFalse(config["providers"]["macro"]["enabled"])
        self.assertEqual(tuple(config["providers"]["china_equity"]["mootdx_frequencies"]), ("day",))
        self.assertEqual(tuple(config["providers"]["china_equity"]["mootdx_index_frequencies"]), ("day",))

        tasks = build_china_equity_tasks(symbols=["600000.SH"], config=config)

        self.assertIn("equity.600000.SH.tencent_metrics", tasks)
        self.assertIn("equity.600000.SH.mootdx_bars", tasks)
        self.assertIn("equity.600000.SH.mootdx_financial_summary", tasks)
        self.assertIn("china.tencent.index_metrics", tasks)
        self.assertIn("equity.sh000001.mootdx_index_day", tasks)
        self.assertNotIn("equity.600000.SH.mootdx_bars_1m", tasks)
        self.assertNotIn("equity.600000.SH.mootdx_realtime", tasks)
        self.assertNotIn("equity.600000.SH.mootdx_order_book", tasks)
        self.assertNotIn("equity.600000.SH.mootdx_shareholders", tasks)
        self.assertNotIn("equity.600000.SH.mootdx_company_profile", tasks)
        self.assertNotIn("equity.600000.SH.mootdx_transactions", tasks)

    def test_explicit_a_share_symbol_uses_stock_deep_profile_even_with_sector(self) -> None:
        config, profile = digital_oracle_collector.apply_a_share_collection_profile(
            {
                "task": "分析半导体里的浦发银行",
                "candidates": [{"symbol": "600000.SH"}],
                "scan_scope": {"sectors": ["半导体"]},
                "metadata": {"ui_mode": "a_share_sector"},
            },
            full_depth_collector_config(),
        )

        self.assertEqual(profile, "stock_deep")
        self.assertEqual(config["candidate_discovery"]["max_candidates"], 15)
        self.assertTrue(config["providers"]["macro"]["enabled"])
        self.assertIn("1m", config["providers"]["china_equity"]["mootdx_frequencies"])
        self.assertTrue(config["providers"]["china_equity"]["mootdx_order_book"])

        tasks = build_china_equity_tasks(symbols=["600000.SH"], config=config)

        self.assertIn("equity.600000.SH.mootdx_bars_1m", tasks)
        self.assertIn("equity.600000.SH.mootdx_order_book", tasks)
        self.assertIn("equity.600000.SH.mootdx_company_profile", tasks)
        self.assertIn("equity.600000.SH.mootdx_transactions", tasks)

    def test_sector_profile_can_collect_china_index_without_candidate_symbols(self) -> None:
        original = digital_oracle_collector.build_china_equity_tasks

        def fake_china_tasks(*, symbols, config):  # type: ignore[no-untyped-def]
            self.assertEqual(symbols, [])
            return {"china.tencent.index_metrics": lambda: {"ok": True}}

        digital_oracle_collector.build_china_equity_tasks = fake_china_tasks
        try:
            output = digital_oracle_collector.collect_market_information(
                {
                    "task": "分析一个没有识别出名称的板块",
                    "candidates": [],
                    "metadata": {"ui_mode": "a_share_sector"},
                },
                {
                    "collector": {
                        "enabled": True,
                        "providers": {
                            "us_equity": {"enabled": False},
                            "china_equity": {
                                "enabled": True,
                                "tencent": True,
                                "tencent_index_metrics": True,
                                "mootdx": False,
                            },
                            "macro": {"enabled": False},
                            "prediction_markets": {"enabled": False},
                            "crypto": {"enabled": False},
                            "web_search": {"enabled": False},
                        },
                    },
                },
            )
        finally:
            digital_oracle_collector.build_china_equity_tasks = original

        self.assertEqual(output["a_share_collection_profile"], "sector_shallow")
        self.assertEqual(output["collection_status"], "ok")
        self.assertIn("china.tencent.index_metrics", output["sources"])

    def test_a_share_macro_question_does_not_trigger_candidate_discovery(self) -> None:
        config, profile = digital_oracle_collector.apply_a_share_collection_profile(
            {
                "task": "分析 A 股宏观流动性和大盘指数风险",
                "candidates": [],
                "question_understanding": {
                    "market_scope": "China A-share macro market",
                    "candidate_scope": "No stock candidates requested",
                },
            },
            full_depth_collector_config(),
        )

        self.assertEqual(profile, "market_macro")
        self.assertFalse(config["candidate_discovery"]["enabled"])
        self.assertTrue(config["providers"]["china_equity"]["tencent_index_metrics"])
        self.assertFalse(config["providers"]["china_equity"]["mootdx"])
        self.assertFalse(config["providers"]["tushare"]["a_share_financials"])
        self.assertFalse(config["providers"]["tushare"]["moneyflow"])
        self.assertTrue(config["providers"]["tushare"]["index_daily"])
        self.assertTrue(config["providers"]["tushare"]["fund_daily"])
        self.assertTrue(config["providers"]["tushare"]["moneyflow_hsgt"])

    def test_a_share_macro_question_auto_universe_is_not_stock_selection(self) -> None:
        self.assertIsNone(
            digital_oracle_collector.infer_auto_candidate_universe(
                "分析 A 股宏观流动性和大盘指数风险"
            )
        )

    def test_a_share_stock_selection_still_triggers_auto_universe(self) -> None:
        self.assertEqual(
            digital_oracle_collector.infer_auto_candidate_universe("A股未来最有潜力的股票"),
            "china_a_share_core",
        )


def build_test_concept_workbook(path: Path) -> Path:
    rows = [
        [
            "代码",
            "证券名称",
            "行业",
            "概念板块",
            "营业收入同比\n2025年三季\n[单位]%",
            "归母净利润同比\n2025年三季\n[单位]%",
            "净资产收益率\n2025年三季\n[单位]%",
            "PE",
            "总市值\n亿元",
        ],
        ["300001", "概念命中", "其他行业", "半导体概念", 10, 20, 12, 20, 100],
        ["600001", "行业误导", "半导体-设计", "人工智能", 50, 50, 20, 15, 200],
    ]
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        archive.writestr("xl/worksheets/sheet1.xml", build_sheet_xml(rows))
    return path


def full_depth_collector_config() -> dict:
    return {
        "candidate_discovery": {"enabled": True, "max_candidates": 15},
        "providers": {
            "macro": {"enabled": True},
            "china_equity": {
                "enabled": True,
                "tencent": True,
                "tencent_index_metrics": True,
                "tencent_index_symbols": ("sh000001",),
                "mootdx": True,
                "mootdx_frequencies": ("day", "week", "month", "1m", "5m", "15m", "30m", "1h"),
                "mootdx_realtime": True,
                "mootdx_intraday": True,
                "mootdx_order_book": True,
                "mootdx_financials": True,
                "mootdx_shareholders": True,
                "mootdx_company_profile": True,
                "mootdx_index_symbols": ("sh000001",),
                "mootdx_index_frequencies": ("day", "week", "month", "1m"),
                "mootdx_transactions": True,
            },
        },
    }


def build_sheet_xml(rows: list[list[object]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, 1):
        cells = []
        for col_index, value in enumerate(row, 1):
            ref = f"{column_name(col_index)}{row_index}"
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
            )
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData>'
        "</worksheet>"
    )


def column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


if __name__ == "__main__":
    unittest.main()
