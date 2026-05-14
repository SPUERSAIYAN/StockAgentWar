from __future__ import annotations

import copy
import unittest

from agents.information_agent import build_structured_information_context
from graph.a_share_auto_trade_graph import build_a_share_auto_trade_graph
from graph.stock_graph import DEFAULT_AGENT_CONFIGS, build_common_analysis_graph, build_stock_graph


INTERNAL_STRUCTURED_NODES = {"bull_cases", "bear_cases", "judge_rulings", "portfolio_decision"}


class DocumentedChainTests(unittest.TestCase):
    def test_stock_graph_uses_documented_chain_nodes(self) -> None:
        graph = build_stock_graph(agent_configs=mock_configs())
        node_names = set(graph.get_graph().nodes)

        self.assertNotIn("a_share_context", node_names)
        self.assertNotIn("skip_trade_plan", node_names)
        self.assertTrue(INTERNAL_STRUCTURED_NODES.issubset(node_names))
        self.assertIn("portfolio_manager", node_names)
        self.assertIn("save_trade_plan", node_names)
        self.assertIn("final_output", node_names)

    def test_a_share_graph_uses_documented_chain_nodes(self) -> None:
        graph = build_a_share_auto_trade_graph(agent_configs=mock_configs())
        node_names = set(graph.get_graph().nodes)

        self.assertNotIn("a_share_context", node_names)
        self.assertNotIn("skip_trade_plan", node_names)
        self.assertTrue(INTERNAL_STRUCTURED_NODES.issubset(node_names))
        self.assertIn("portfolio_manager", node_names)
        self.assertIn("save_trade_plan", node_names)
        self.assertIn("final_output", node_names)

    def test_common_analysis_graph_stops_after_information_analysis(self) -> None:
        graph = build_common_analysis_graph(agent_configs=mock_configs())
        node_names = set(graph.get_graph().nodes)

        self.assertIn("question_planning", node_names)
        self.assertIn("information_analysis", node_names)
        self.assertTrue(
            {
                "bull_debate",
                "bear_debate",
                "bull_cases",
                "bear_cases",
                "judge_decision",
                "judge_rulings",
                "risk_review",
                "portfolio_manager",
                "portfolio_decision",
                "save_trade_plan",
                "final_output",
            }.isdisjoint(node_names)
        )

    def test_stock_graph_runs_through_final_output_with_no_trade_plan(self) -> None:
        graph = build_stock_graph(agent_configs=mock_configs())
        result = graph.invoke(
            {
                "task": "Analyze AAPL",
                "candidates": [{"symbol": "AAPL"}],
                "metadata": {},
            }
        )

        self.assertEqual(result["final_decision"]["action"], "NO_TRADE")
        self.assertIsNone(result["metadata"]["trade_plan_file"])
        self.assertIn("final_output", result)
        self.assertNotIn("a_share_context", result)

    def test_information_context_is_structured_from_provider_data(self) -> None:
        output = build_structured_information_context(
            {"candidates": [{"symbol": "AAPL", "score": 75, "reason": "test candidate"}]},
            {
                "collection_status": "ok",
                "source_count": 1,
                "error_count": 0,
                "sources": {
                    "equity.AAPL.price_daily": {
                        "latest": {"close": 120.5},
                        "return_20_bar_pct": 4.2,
                        "avg_volume_20": 1000000,
                    }
                },
                "errors": {},
            },
        )

        self.assertEqual(output["stock_pool"][0]["symbol"], "AAPL")
        self.assertEqual(output["stock_pool"][0]["price"], 120.5)
        self.assertTrue(output["sector_summary"])
        self.assertIn("confidence_level", output)

    def test_information_context_empty_without_provider_data(self) -> None:
        output = build_structured_information_context(
            {"candidates": [{"symbol": "AAPL"}]},
            {"collection_status": "empty", "sources": {}, "errors": {}},
        )

        self.assertEqual(output["stock_pool"], [])
        self.assertEqual(output["sector_summary"], [])
        self.assertTrue(output["data_gaps"])


def mock_configs():
    configs = copy.deepcopy(DEFAULT_AGENT_CONFIGS)
    configs["information"] = {
        **configs["information"],
        "collector": {"enabled": False},
    }
    return configs


if __name__ == "__main__":
    unittest.main()
