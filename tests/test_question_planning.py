from __future__ import annotations

import unittest

from agents.question_planning_agent import parse_planner_json, sanitize_question_plan
from agents import information_workflow


class QuestionPlanningTests(unittest.TestCase):
    def test_parse_json_from_markdown_fence(self) -> None:
        parsed = parse_planner_json(
            """```json
{"question_understanding": {"rewritten_question": "x"}, "signal_plan": {"selected_provider_groups": ["us_equity"]}}
```"""
        )
        self.assertEqual(parsed["question_understanding"]["rewritten_question"], "x")

    def test_a_share_question_constrains_to_china_and_macro(self) -> None:
        plan = sanitize_question_plan(
            {
                "question_understanding": {
                    "rewritten_question": "A股市场极短期具有上涨潜力的个股/板块识别",
                    "market_scope": "China A-share",
                },
                "signal_plan": {
                    "selected_provider_groups": ["china_equity", "us_equity", "crypto", "macro", "not_real"],
                    "selected_signals": [
                        {"id": "china.realtime_metrics", "provider_group": "china_equity", "reason": "A-share quote data"},
                        {"id": "crypto.risk", "provider_group": "crypto", "reason": "noise"},
                    ],
                },
            },
            {"task": "明天买哪只股票", "candidates": [], "metadata": {"ui_mode": "a_share_daily"}},
        )
        self.assertEqual(plan["signal_plan"]["selected_provider_groups"], ["china_equity", "macro"])
        rejected = {item["provider_group"] for item in plan["signal_plan"]["rejected_provider_groups"]}
        self.assertIn("crypto", rejected)
        self.assertIn("us_equity", rejected)

    def test_us_symbols_keep_us_equity_and_macro(self) -> None:
        plan = sanitize_question_plan(
            {
                "question_understanding": {"market_scope": "US equities"},
                "signal_plan": {"selected_provider_groups": ["us_equity", "macro"]},
            },
            {"task": "Analyze AAPL and MSFT", "candidates": [{"symbol": "AAPL"}, {"symbol": "MSFT"}]},
        )
        self.assertEqual(plan["signal_plan"]["selected_provider_groups"], ["us_equity", "macro"])

    def test_information_workflow_uses_planner_groups(self) -> None:
        state = {
            "task": "明天买哪只股票",
            "question_understanding": {
                "rewritten_question": "A股市场极短期具有上涨潜力的个股/板块识别",
                "market_scope": "China A-share",
                "primary_time_window": "1-5 trading days",
            },
            "signal_plan": {"selected_provider_groups": ["china_equity", "macro"]},
        }
        workflow = information_workflow.build_information_workflow(state)
        provider_selection = information_workflow.select_information_providers(state, workflow, {})
        self.assertEqual(
            set(provider_selection["selected_groups"]),
            {"china_equity", "macro"},
        )
        self.assertEqual(
            workflow["question_decomposition"]["time_window"],
            "very_short_term_1_to_5_trading_days",
        )


if __name__ == "__main__":
    unittest.main()
