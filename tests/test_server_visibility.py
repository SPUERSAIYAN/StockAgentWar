from __future__ import annotations

import json
import unittest

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
        for node in set(A_SHARE_VISIBLE_ORDER) - set(COMMON_VISIBLE_ORDER):
            self.assertNotIn(node, stage_nodes)
            self.assertNotIn(node, status_nodes)
        self.assertEqual(complete_events[-1]["final_output"], complete_events[-1]["state"]["info_report"])
        self.assertEqual(complete_events[-1]["state"]["final_output"], complete_events[-1]["final_output"])
        for key in INTERNAL_NODES | {"final_decision", "trade_plan", "alternative_scenarios"}:
            self.assertNotIn(key, complete_events[-1]["state"])


if __name__ == "__main__":
    unittest.main()
