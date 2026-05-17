from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from math import floor
from typing import Any

from agents.information_agent import run_prompt_agent
from agents.prompt_loader import load_agent_prompt
from schemas.state import AgentRuntimeConfig


TRADE_PLAN_BEGIN = "BEGIN_TRADE_PLAN_JSON"
TRADE_PLAN_END = "END_TRADE_PLAN_JSON"
VALID_FINAL_ACTIONS = {"BUY", "HOLD", "WAIT", "NO_TRADE"}


class PortfolioManagerAgent:
    def __init__(self, config: AgentRuntimeConfig):
        self.config = config
        self.prompt = load_agent_prompt("portfolio_manager_agent.md")

    def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        return run_prompt_agent(
            config=self.config,
            state=state,
            output_key="manager_report",
            prompt_template=self.prompt,
        )


def build_portfolio_decision(
    state: dict[str, Any],
    config: AgentRuntimeConfig,
) -> dict[str, Any]:
    manager_report = str(state.get("manager_report") or "")
    portfolio_context = dict(state.get("portfolio_context", {}) or {})
    sizing = dict(config.get("position_sizing", {}) or {})

    available_capital = float(portfolio_context.get("available_capital") or 0)
    if available_capital <= 0:
        available_capital = float(config.get("simulated_initial_capital", 1_000_000))

    max_single_pct = float(
        portfolio_context.get("max_position_pct")
        or sizing.get("max_single_position_pct")
        or 20
    )
    max_total_pct = float(sizing.get("max_total_exposure_pct") or 80)

    payload = extract_trade_plan_payload(manager_report)
    if payload is None:
        return build_wait_decision("总经理报告未提供有效交易计划结构块。")

    final_decision = as_dict(payload.get("final_decision"))
    requested_action = normalize_action(final_decision.get("action"))
    reasoning = str(final_decision.get("reasoning") or "总经理报告未提供明确决策理由。")
    stock_pool_by_symbol = index_by_symbol(state.get("stock_pool", []))

    monitored_stocks: list[dict[str, Any]] = []
    if requested_action == "BUY":
        plan = as_dict(payload.get("trade_plan"))
        monitored_stocks = normalize_monitored_stocks(
            plan.get("monitored_stocks", []),
            stock_pool_by_symbol=stock_pool_by_symbol,
            available_capital=available_capital,
            max_single_pct=max_single_pct,
            max_total_pct=max_total_pct,
        )
        if not monitored_stocks:
            requested_action = "WAIT"
            reasoning = "总经理报告提出 BUY，但未提供有效交易计划结构块标的。"

    plan_payload = as_dict(payload.get("trade_plan"))
    trade_plan = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "monitored_stocks": monitored_stocks,
        "position_sizing_rationale": str(
            plan_payload.get("position_sizing_rationale")
            or (
                f"单只仓位不超过 {max_single_pct:.0f}%，总仓位不超过 {max_total_pct:.0f}%；"
                "数量按 A 股 100 股整数倍取整。"
            )
        ),
    }
    confidence = clamp_confidence(payload.get("manager_confidence"))

    return {
        "final_decision": {
            "action": requested_action,
            "reasoning": reasoning,
        },
        "trade_plan": trade_plan,
        "alternative_scenarios": normalize_alternative_scenarios(payload.get("alternative_scenarios")),
        "manager_confidence": round(confidence, 2),
    }


def extract_trade_plan_payload(manager_report: str) -> dict[str, Any] | None:
    match = re.search(
        rf"{TRADE_PLAN_BEGIN}\s*(.*?)\s*{TRADE_PLAN_END}",
        manager_report,
        flags=re.DOTALL,
    )
    if not match:
        return None
    block = match.group(1).strip()
    if block.startswith("```"):
        block = re.sub(r"^```(?:json)?\s*", "", block, flags=re.IGNORECASE)
        block = re.sub(r"\s*```$", "", block)
    try:
        payload = json.loads(block)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def normalize_monitored_stocks(
    items: Any,
    *,
    stock_pool_by_symbol: dict[str, dict[str, Any]],
    available_capital: float,
    max_single_pct: float,
    max_total_pct: float,
) -> list[dict[str, Any]]:
    rows = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    prepared: list[dict[str, Any]] = []
    today = datetime.now().date()
    default_valid_until = today + timedelta(days=30)

    for item in rows:
        symbol = str(item.get("symbol") or "").strip()
        if not symbol:
            continue
        stock = stock_pool_by_symbol.get(symbol, {})
        price = first_float(item, "price", "current_price", "latest_price") or to_float(stock.get("price"))
        buy_trigger = first_float(item, "buy_trigger_price", "entry_price")
        take_profit = first_float(item, "take_profit_price", "sell_trigger_price", "target_price")
        sell_trigger = first_float(item, "sell_trigger_price", "take_profit_price", "target_price")
        stop_loss = first_float(item, "stop_loss_price", "stop_loss")
        allocation_pct = first_float(item, "allocation_pct", "weight_pct", "position_pct")
        allocation_amount = first_float(item, "allocation_amount")
        if allocation_pct is None and allocation_amount is not None and available_capital > 0:
            allocation_pct = allocation_amount / available_capital * 100
        if not all(
            value is not None and value > 0
            for value in (price, buy_trigger, take_profit, sell_trigger, stop_loss, allocation_pct)
        ):
            continue
        allocation_pct = min(float(allocation_pct), max_single_pct)
        prepared.append(
            {
                "raw": item,
                "stock": stock,
                "symbol": symbol,
                "price": float(price),
                "allocation_pct": allocation_pct,
                "buy_trigger_price": float(buy_trigger),
                "sell_trigger_price": float(sell_trigger),
                "stop_loss_price": float(stop_loss),
                "take_profit_price": float(take_profit),
                "valid_from": str(item.get("valid_from") or today.isoformat()),
                "valid_until": str(item.get("valid_until") or default_valid_until.isoformat()),
                "expiry_action": str(item.get("expiry_action") or "REVIEW"),
            }
        )

    total_pct = sum(row["allocation_pct"] for row in prepared)
    if total_pct > max_total_pct and total_pct > 0:
        scale = max_total_pct / total_pct
        for row in prepared:
            row["allocation_pct"] *= scale

    normalized: list[dict[str, Any]] = []
    for row in prepared:
        item = row["raw"]
        allocation_pct = round(row["allocation_pct"], 2)
        allocation_amount = round(available_capital * allocation_pct / 100, 2)
        max_quantity = int(floor(allocation_amount / row["price"] / 100) * 100)
        requested_quantity = to_float(item.get("quantity"))
        quantity = (
            int(floor(requested_quantity / 100) * 100)
            if requested_quantity is not None
            else max_quantity
        )
        quantity = min(quantity, max_quantity)
        if quantity <= 0:
            continue
        normalized.append(
            {
                "symbol": row["symbol"],
                "name": item.get("name") or row["stock"].get("name", ""),
                "allocation_pct": allocation_pct,
                "allocation_amount": allocation_amount,
                "quantity": quantity,
                "buy_trigger_price": round(row["buy_trigger_price"], 2),
                "sell_trigger_price": round(row["sell_trigger_price"], 2),
                "stop_loss_price": round(row["stop_loss_price"], 2),
                "take_profit_price": round(row["take_profit_price"], 2),
                "valid_from": row["valid_from"],
                "valid_until": row["valid_until"],
                "expiry_action": row["expiry_action"],
                "conditions": [
                    {
                        "type": "PRICE_BELOW",
                        "price": round(row["buy_trigger_price"], 2),
                        "action": "BUY",
                        "quantity": quantity,
                    },
                    {
                        "type": "PRICE_ABOVE",
                        "price": round(row["sell_trigger_price"], 2),
                        "action": "SELL",
                        "quantity": quantity,
                    },
                ],
            }
        )
    return normalized


def build_wait_decision(reasoning: str) -> dict[str, Any]:
    return {
        "final_decision": {
            "action": "WAIT",
            "reasoning": reasoning,
        },
        "trade_plan": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "monitored_stocks": [],
            "position_sizing_rationale": "总经理报告未提供可解析的交易计划结构块。",
        },
        "alternative_scenarios": normalize_alternative_scenarios(None),
        "manager_confidence": 0.2,
    }


def normalize_action(value: Any) -> str:
    action = str(value or "WAIT").upper()
    return action if action in VALID_FINAL_ACTIONS else "WAIT"


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_alternative_scenarios(value: Any) -> list[dict[str, str]]:
    if isinstance(value, list):
        scenarios = [
            {
                "scenario": str(item.get("scenario") or ""),
                "action": str(item.get("action") or ""),
            }
            for item in value
            if isinstance(item, dict) and (item.get("scenario") or item.get("action"))
        ]
        if scenarios:
            return scenarios
    return [
        {
            "scenario": "大盘突发利空或流动性急剧收缩",
            "action": "暂停新买入，按总经理报告的暂停条件重新评估。",
        },
        {
            "scenario": "关键数据源不可用",
            "action": "保持观察状态，待数据恢复后重新生成总经理交易计划。",
        },
    ]


def clamp_confidence(value: Any) -> float:
    confidence = to_float(value)
    if confidence is None:
        return 0.35
    return max(0.0, min(confidence, 1.0))


def first_float(item: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = to_float(item.get(key))
        if value is not None:
            return value
    return None


def index_by_symbol(items: Any) -> dict[str, dict[str, Any]]:
    rows = items if isinstance(items, list) else []
    return {
        str(item.get("symbol", "")): item
        for item in rows
        if isinstance(item, dict) and item.get("symbol")
    }


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
