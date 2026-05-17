from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import server


INTERNAL_NODES = {"bull_cases", "bear_cases", "judge_rulings", "portfolio_decision"}
COMMON_VISIBLE_ORDER = [
    "question_planning",
    "information_analysis",
]
A_SHARE_VISIBLE_ORDER = [
    "question_planning",
    "information_analysis",
    "bull_debate",
    "bear_debate",
    "judge_decision",
    "risk_review",
    "portfolio_manager",
    "save_trade_plan",
]


class ServerVisibilityTests(unittest.TestCase):
    def test_health_stage_sets_hide_internal_nodes(self) -> None:
        response = server.health()

        common_ids = [stage["id"] for stage in response["stage_sets"]["common"]]
        a_share_ids = [stage["id"] for stage in response["stage_sets"]["a_share"]]

        self.assertEqual(common_ids, COMMON_VISIBLE_ORDER)
        self.assertEqual(a_share_ids, A_SHARE_VISIBLE_ORDER)
        self.assertTrue(INTERNAL_NODES.isdisjoint(common_ids))
        self.assertTrue(INTERNAL_NODES.isdisjoint(a_share_ids))

        top_level_ids = [stage["id"] for stage in response["stages"]]
        self.assertEqual(top_level_ids, COMMON_VISIBLE_ORDER)
        self.assertTrue(INTERNAL_NODES.isdisjoint(top_level_ids))
        self.assertNotIn("openrouter_key_ready", response)

    def test_openrouter_stream_requires_frontend_api_key(self) -> None:
        request = server.DecisionRequest(
            task="Analyze market",
            symbols="",
            mode="openrouter",
            openrouter_api_key="",
            config_path="config.yaml",
        )

        events = [json.loads(line) for line in server.stream_decision(request)]
        error_events = [event for event in events if event["type"] == "error"]

        self.assertEqual(len(error_events), 1)
        self.assertIn("请先填写 OpenRouter API Key", error_events[0]["message"])

    def test_resolve_agent_configs_injects_frontend_api_key(self) -> None:
        request = server.DecisionRequest(
            task="Analyze market",
            symbols="",
            mode="openrouter",
            openrouter_api_key="sk-test",
            config_path="config.yaml",
        )

        configs = server.resolve_agent_configs(request)

        openrouter_models = [
            config["model"]
            for config in configs.values()
            if isinstance(config.get("model"), dict)
            and config["model"].get("provider") == "openrouter"
        ]
        self.assertTrue(openrouter_models)
        self.assertTrue(all(model.get("api_key") == "sk-test" for model in openrouter_models))

    def test_public_state_hides_raw_structured_fields(self) -> None:
        public = server.public_state(
            {
                "question_plan_report": "plan",
                "info_report": "info",
                "bull_case": "bull",
                "bear_case": "bear",
                "judge_decision": "judge",
                "risk_report": "risk",
                "manager_report": "manager",
                "manager_confidence": 0.7,
                "final_output": "final",
                "bull_cases": [{"symbol": "AAPL"}],
                "bear_cases": [{"symbol": "AAPL"}],
                "judge_rulings": [{"symbol": "AAPL"}],
                "final_decision": {"action": "BUY"},
                "trade_plan": {"monitored_stocks": []},
                "alternative_scenarios": [],
                "metadata": {"trade_plan_file": None, "ui_mode": "mock"},
            }
        )

        self.assertEqual(public["manager_confidence"], 0.7)
        self.assertEqual(public["metadata"], {"trade_plan_file": None})
        for key in (
            "bull_cases",
            "bear_cases",
            "judge_rulings",
            "final_decision",
            "trade_plan",
            "alternative_scenarios",
        ):
            self.assertNotIn(key, public)

    def test_common_stream_stops_after_information_analysis(self) -> None:
        request = server.DecisionRequest(
            task="Analyze tomorrow's A-share direction",
            symbols="",
            mode="mock",
            config_path="config.yaml",
        )

        events = [json.loads(line) for line in server.stream_decision(request)]
        stage_nodes = [event["node"] for event in events if event["type"] == "stage"]
        status_nodes = [event["node"] for event in events if event["type"] == "stage_status"]
        complete_events = [event for event in events if event["type"] == "complete"]

        self.assertTrue(INTERNAL_NODES.isdisjoint(stage_nodes))
        self.assertTrue(INTERNAL_NODES.isdisjoint(status_nodes))
        self.assertEqual(stage_nodes, COMMON_VISIBLE_ORDER)
        self.assertEqual(status_nodes, COMMON_VISIBLE_ORDER)
        self.assertEqual(len(complete_events), 1)
        for node in set(A_SHARE_VISIBLE_ORDER) - set(COMMON_VISIBLE_ORDER):
            self.assertNotIn(node, stage_nodes)
            self.assertNotIn(node, status_nodes)
        self.assertEqual(complete_events[-1]["final_output"], complete_events[-1]["state"]["info_report"])
        self.assertEqual(complete_events[-1]["state"]["final_output"], complete_events[-1]["final_output"])
        for key in INTERNAL_NODES | {"final_decision", "trade_plan", "alternative_scenarios"}:
            self.assertNotIn(key, complete_events[-1]["state"])

    def test_a_share_stream_keeps_full_decision_chain(self) -> None:
        request = server.DecisionRequest(
            task="Scan A-share market",
            symbols="",
            mode="a_share_daily",
            config_path="config.yaml",
        )

        with (
            patch.object(server, "resolve_agent_configs", return_value={}),
            patch.object(server, "build_a_share_auto_trade_graph", return_value=FakeAshareGraph()),
        ):
            events = [json.loads(line) for line in server.stream_decision(request)]

        stage_nodes = [event["node"] for event in events if event["type"] == "stage"]
        status_nodes = [event["node"] for event in events if event["type"] == "stage_status"]
        complete_events = [event for event in events if event["type"] == "complete"]

        self.assertEqual(stage_nodes, A_SHARE_VISIBLE_ORDER)
        self.assertEqual(status_nodes, A_SHARE_VISIBLE_ORDER)
        self.assertEqual(complete_events[-1]["final_output"], "final")

    def test_trade_plan_report_displays_without_plan_file(self) -> None:
        report = server.render_trade_plan_report(
            {"metadata": {"trade_plan_file": None}},
            {
                "final_decision": {"action": "BUY", "reasoning": "test buy"},
                "trade_plan": {
                    "monitored_stocks": [
                        {
                            "symbol": "600000.SH",
                            "name": "浦发银行",
                            "quantity": 100,
                            "allocation_pct": 10,
                            "buy_trigger_price": 9.8,
                            "sell_trigger_price": 11,
                            "stop_loss_price": 9,
                            "take_profit_price": 11,
                            "valid_from": "2026-05-17",
                            "valid_until": "2026-06-16",
                        }
                    ]
                },
            },
        )

        self.assertIn("仅展示，不写入交易计划 JSON 文件", report)
        self.assertNotIn("计划文件", report)


class FakeAshareGraph:
    def stream(self, inputs, stream_mode):
        self.inputs = inputs
        self.stream_mode = stream_mode
        yield {"question_planning": {"question_plan_report": "plan"}}
        yield {"information_analysis": {"info_report": "info"}}
        yield {"bull_debate": {"bull_case": "bull"}}
        yield {"bear_debate": {"bear_case": "bear"}}
        yield {"bull_cases": {"bull_cases": []}}
        yield {"bear_cases": {"bear_cases": []}}
        yield {"judge_decision": {"judge_decision": "judge"}}
        yield {"judge_rulings": {"judge_rulings": []}}
        yield {"risk_review": {"risk_report": "risk"}}
        yield {"portfolio_manager": {"manager_report": "manager", "manager_confidence": 0.8}}
        yield {"portfolio_decision": {"final_decision": {"action": "WAIT", "reasoning": "test"}}}
        yield {"save_trade_plan": {"metadata": {"trade_plan_file": None}}}
        yield {"final_output": {"final_output": "final"}}


if __name__ == "__main__":
    unittest.main()
