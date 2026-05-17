from __future__ import annotations

import json
import unittest

from agents.portfolio_manager_agent import build_portfolio_decision


class PortfolioTradePlanTests(unittest.TestCase):
    def test_trade_plan_comes_from_manager_report_block(self) -> None:
        output = build_portfolio_decision(
            {
                "manager_report": manager_report(
                    {
                        "final_decision": {"action": "BUY", "reasoning": "总经理选择浦发银行。"},
                        "manager_confidence": 0.76,
                        "trade_plan": {
                            "position_sizing_rationale": "按总经理报告仓位展示。",
                            "monitored_stocks": [
                                {
                                    "symbol": "600000.SH",
                                    "name": "浦发银行",
                                    "price": 10,
                                    "allocation_pct": 10,
                                    "quantity": 1000,
                                    "buy_trigger_price": 9.8,
                                    "sell_trigger_price": 11,
                                    "stop_loss_price": 9,
                                    "take_profit_price": 11,
                                }
                            ],
                        },
                        "alternative_scenarios": [],
                    }
                ),
                "stock_pool": [
                    {"symbol": "000001.SZ", "name": "平安银行", "price": 12, "information_score": 95},
                    {"symbol": "600000.SH", "name": "浦发银行", "price": 10, "information_score": 60},
                ],
                "judge_rulings": [{"symbol": "000001.SZ", "ruling": "STRONG_BUY"}],
            },
            portfolio_config(),
        )

        stocks = output["trade_plan"]["monitored_stocks"]
        self.assertEqual(output["final_decision"]["action"], "BUY")
        self.assertEqual([stock["symbol"] for stock in stocks], ["600000.SH"])
        self.assertEqual(output["manager_confidence"], 0.76)

    def test_wait_or_no_trade_does_not_keep_monitored_stocks(self) -> None:
        for action in ("WAIT", "NO_TRADE"):
            with self.subTest(action=action):
                output = build_portfolio_decision(
                    {
                        "manager_report": manager_report(
                            {
                                "final_decision": {"action": action, "reasoning": "总经理要求等待。"},
                                "manager_confidence": 0.4,
                                "trade_plan": {
                                    "position_sizing_rationale": "不建仓。",
                                    "monitored_stocks": [
                                        {
                                            "symbol": "600000.SH",
                                            "price": 10,
                                            "allocation_pct": 10,
                                            "quantity": 100,
                                            "buy_trigger_price": 9.8,
                                            "sell_trigger_price": 11,
                                            "stop_loss_price": 9,
                                            "take_profit_price": 11,
                                        }
                                    ],
                                },
                            }
                        )
                    },
                    portfolio_config(),
                )

                self.assertEqual(output["final_decision"]["action"], action)
                self.assertEqual(output["trade_plan"]["monitored_stocks"], [])

    def test_missing_or_invalid_block_waits_without_stock_pool_fallback(self) -> None:
        for manager_text in ("没有结构块", "BEGIN_TRADE_PLAN_JSON\n{bad json}\nEND_TRADE_PLAN_JSON"):
            with self.subTest(manager_text=manager_text):
                output = build_portfolio_decision(
                    {
                        "manager_report": manager_text,
                        "stock_pool": [{"symbol": "600000.SH", "price": 10, "information_score": 99}],
                        "judge_rulings": [{"symbol": "600000.SH", "ruling": "STRONG_BUY"}],
                    },
                    portfolio_config(),
                )

                self.assertEqual(output["final_decision"]["action"], "WAIT")
                self.assertIn("总经理报告未提供有效交易计划结构块", output["final_decision"]["reasoning"])
                self.assertEqual(output["trade_plan"]["monitored_stocks"], [])

    def test_quantity_is_rounded_down_to_100_share_lot(self) -> None:
        output = build_portfolio_decision(
            {
                "manager_report": manager_report(
                    {
                        "final_decision": {"action": "BUY", "reasoning": "数量需要规范化。"},
                        "trade_plan": {
                            "monitored_stocks": [
                                {
                                    "symbol": "600000.SH",
                                    "price": 10,
                                    "allocation_pct": 10,
                                    "quantity": 150,
                                    "buy_trigger_price": 9.8,
                                    "sell_trigger_price": 11,
                                    "stop_loss_price": 9,
                                    "take_profit_price": 11,
                                }
                            ]
                        },
                    }
                )
            },
            portfolio_config(),
        )

        self.assertEqual(output["trade_plan"]["monitored_stocks"][0]["quantity"], 100)

    def test_position_limits_are_applied(self) -> None:
        output = build_portfolio_decision(
            {
                "manager_report": manager_report(
                    {
                        "final_decision": {"action": "BUY", "reasoning": "仓位需要压缩。"},
                        "trade_plan": {
                            "monitored_stocks": [
                                {
                                    "symbol": "600000.SH",
                                    "price": 10,
                                    "allocation_pct": 20,
                                    "quantity": 2000,
                                    "buy_trigger_price": 9.8,
                                    "sell_trigger_price": 11,
                                    "stop_loss_price": 9,
                                    "take_profit_price": 11,
                                },
                                {
                                    "symbol": "000001.SZ",
                                    "price": 10,
                                    "allocation_pct": 20,
                                    "quantity": 2000,
                                    "buy_trigger_price": 9.8,
                                    "sell_trigger_price": 11,
                                    "stop_loss_price": 9,
                                    "take_profit_price": 11,
                                },
                            ]
                        },
                    }
                )
            },
            portfolio_config(max_single=10, max_total=15),
        )

        stocks = output["trade_plan"]["monitored_stocks"]
        self.assertEqual([stock["allocation_pct"] for stock in stocks], [7.5, 7.5])
        self.assertEqual([stock["quantity"] for stock in stocks], [700, 700])


def manager_report(payload: dict) -> str:
    return (
        "总经理报告正文。\n"
        "BEGIN_TRADE_PLAN_JSON\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n"
        "END_TRADE_PLAN_JSON"
    )


def portfolio_config(max_single: int = 20, max_total: int = 80) -> dict:
    return {
        "simulated_initial_capital": 100_000,
        "position_sizing": {
            "max_single_position_pct": max_single,
            "max_total_exposure_pct": max_total,
        },
    }


if __name__ == "__main__":
    unittest.main()
