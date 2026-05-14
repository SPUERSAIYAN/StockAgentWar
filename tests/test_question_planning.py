from __future__ import annotations

import unittest

from agents import information_workflow
from agents.question_planning_agent import (
    QuestionPlanningAgent,
    normalize_question_plan,
    parse_planner_json,
)
from collectors import digital_oracle_collector


class QuestionPlanningTests(unittest.TestCase):
    def test_agent_parses_mock_json_provider_selection(self) -> None:
        agent = QuestionPlanningAgent(
            {
                "name": "question_planning",
                "prompt_file": "question_planning_agent.md",
                "model": {"provider": "mock", "model": "mock-question-planning"},
            }
        )
        result = agent({"task": "Analyze AAPL", "candidates": [{"symbol": "AAPL"}]})

        self.assertEqual(result["provider_selection"]["selected_groups"], ["us_equity", "macro"])
        self.assertTrue(result["provider_selection"]["providers"]["us_equity"]["enabled"])
        self.assertFalse(result["provider_selection"]["providers"]["china_equity"]["enabled"])

    def test_agent_parses_mock_json_for_a_share_selection(self) -> None:
        agent = QuestionPlanningAgent(
            {
                "name": "question_planning",
                "prompt_file": "question_planning_agent.md",
                "model": {"provider": "mock", "model": "mock-question-planning"},
            }
        )
        result = agent({"task": "分析 A股 600519", "candidates": [{"symbol": "600519"}]})

        self.assertEqual(result["provider_selection"]["selected_groups"], ["china_equity", "macro"])
        self.assertTrue(result["provider_selection"]["providers"]["china_equity"]["enabled"])
        self.assertFalse(result["provider_selection"]["providers"]["us_equity"]["enabled"])

    def test_agent_parses_mock_json_for_a_share_sector_selection(self) -> None:
        agent = QuestionPlanningAgent(
            {
                "name": "question_planning",
                "prompt_file": "question_planning_agent.md",
                "model": {"provider": "mock", "model": "mock-question-planning"},
            }
        )
        result = agent({"task": "分析 A 股半导体板块", "candidates": []})

        self.assertEqual(result["provider_selection"]["selected_groups"], ["china_equity", "macro"])
        self.assertTrue(result["provider_selection"]["providers"]["china_equity"]["enabled"])
        self.assertFalse(result["provider_selection"]["providers"]["us_equity"]["enabled"])
        self.assertEqual(result["question_understanding"]["sector_terms"], ["半导体"])

    def test_parse_json_from_markdown_fence(self) -> None:
        parsed = parse_planner_json(
            """```json
{"question_understanding": {"rewritten_question": "x"}, "provider_selection": {"selected_groups": ["macro"], "providers": {}, "rejected_groups": []}}
```"""
        )
        self.assertEqual(parsed["question_understanding"]["rewritten_question"], "x")

    def test_normalizes_sector_terms(self) -> None:
        result = normalize_question_plan(
            {
                "question_understanding": {
                    "rewritten_question": "x",
                    "sector_terms": "半导体, 白酒，人工智能",
                },
                "provider_selection": {
                    "selected_groups": ["china_equity"],
                    "providers": {},
                    "rejected_groups": [],
                },
            }
        )

        self.assertEqual(result["question_understanding"]["sector_terms"], ["半导体", "白酒", "人工智能"])

    def test_invalid_json_fails(self) -> None:
        with self.assertRaises(ValueError):
            parse_planner_json("not json")

    def test_missing_model_config_fails(self) -> None:
        with self.assertRaises(ValueError):
            QuestionPlanningAgent({"prompt_file": "question_planning_agent.md"})

    def test_unknown_provider_fails(self) -> None:
        with self.assertRaises(ValueError):
            normalize_question_plan(
                {
                    "question_understanding": {"rewritten_question": "x"},
                    "provider_selection": {
                        "selected_groups": ["macro", "not_real"],
                        "providers": {},
                        "rejected_groups": [],
                    },
                }
            )

    def test_empty_provider_selection_fails(self) -> None:
        with self.assertRaises(ValueError):
            normalize_question_plan(
                {
                    "question_understanding": {"rewritten_question": "x"},
                    "provider_selection": {
                        "selected_groups": [],
                        "providers": {},
                        "rejected_groups": [],
                    },
                }
            )

    def test_information_workflow_uses_planner_selection_only(self) -> None:
        state = {
            "task": "Analyze AAPL and MSFT",
            "candidates": [{"symbol": "AAPL"}, {"symbol": "MSFT"}],
            "question_understanding": {
                "rewritten_question": "Macro-only test",
                "market_scope": "US equities",
                "time_window": "3-12 months",
            },
            "provider_selection": {
                "selected_groups": ["macro"],
                "providers": {
                    "macro": {"enabled": True, "reason": "Planner selected macro only."},
                    "us_equity": {"enabled": False, "reason": "Planner rejected direct equity data."},
                },
                "rejected_groups": ["us_equity", "china_equity", "prediction_markets", "crypto", "web_search"],
            },
        }

        workflow = information_workflow.build_information_workflow(state)
        provider_selection = information_workflow.select_information_providers(state, workflow, {})

        self.assertEqual(provider_selection["selected_groups"], ["macro"])
        self.assertTrue(provider_selection["providers"]["macro"]["enabled"])
        self.assertFalse(provider_selection["providers"]["us_equity"]["enabled"])

    def test_candidate_discovery_not_called_when_china_equity_disabled(self) -> None:
        original = digital_oracle_collector.discover_candidate_universe

        def fail_if_called(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("candidate discovery should not be called")

        digital_oracle_collector.discover_candidate_universe = fail_if_called
        try:
            result = digital_oracle_collector.collect_market_information(
                {"task": "No symbol test", "candidates": []},
                {
                    "name": "information",
                    "collector": {
                        "enabled": True,
                        "providers": {
                            "us_equity": {"enabled": False},
                            "china_equity": {"enabled": False},
                            "macro": {"enabled": False},
                            "prediction_markets": {"enabled": False},
                            "crypto": {"enabled": False},
                            "web_search": {"enabled": False},
                        },
                    },
                },
            )
        finally:
            digital_oracle_collector.discover_candidate_universe = original

        self.assertEqual(result["collection_status"], "empty")


if __name__ == "__main__":
    unittest.main()
