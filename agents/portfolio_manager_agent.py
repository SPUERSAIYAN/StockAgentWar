from __future__ import annotations

from datetime import datetime, timedelta
from math import floor
from typing import Any

from agents.information_agent import run_prompt_agent
from agents.prompt_loader import load_agent_prompt
from schemas.state import AgentRuntimeConfig


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
    portfolio_context = dict(state.get("portfolio_context", {}) or {})
    sizing = dict(config.get("position_sizing", {}) or {})
    risk_control = dict(config.get("risk_control", {}) or {})

    available_capital = float(portfolio_context.get("available_capital") or 0)
    if available_capital <= 0:
        available_capital = float(config.get("simulated_initial_capital", 1_000_000))

    max_single_pct = float(
        portfolio_context.get("max_position_pct")
        or sizing.get("max_single_position_pct")
        or 20
    )
    max_total_pct = float(sizing.get("max_total_exposure_pct") or 80)
    stop_loss_pct = float(risk_control.get("stop_loss_pct") or 8)
    take_profit_pct = float(risk_control.get("take_profit_pct") or 20)

    stock_pool = list(state.get("stock_pool", []) or [])
    bull_by_symbol = index_by_symbol(state.get("bull_cases", []))
    bear_by_symbol = index_by_symbol(state.get("bear_cases", []))
    selected = select_purchase_candidates(stock_pool, state.get("judge_rulings", []))

    monitored_stocks: list[dict[str, Any]] = []
    per_stock_pct = min(max_single_pct, max_total_pct / max(len(selected), 1))
    today = datetime.now().date()
    valid_until = today + timedelta(days=30)

    for candidate in selected:
        price = to_float(candidate.get("price"))
        if not price or price <= 0:
            continue

        symbol = str(candidate.get("symbol", ""))
        allocation_pct = per_stock_pct
        allocation_amount = round(available_capital * allocation_pct / 100, 2)
        quantity = int(floor(allocation_amount / price / 100) * 100)
        if quantity <= 0:
            continue

        bull_case = bull_by_symbol.get(symbol, {})
        bear_case = bear_by_symbol.get(symbol, {})
        buy_trigger = to_float(bull_case.get("buy_trigger_price")) or round(price * 0.99, 2)
        target_price = to_float(bull_case.get("target_price")) or round(price * (1 + take_profit_pct / 100), 2)
        stop_loss = to_float(bear_case.get("downside_price")) or round(price * (1 - stop_loss_pct / 100), 2)

        monitored_stocks.append(
            {
                "symbol": symbol,
                "name": candidate.get("name", ""),
                "allocation_pct": round(allocation_pct, 2),
                "allocation_amount": allocation_amount,
                "quantity": quantity,
                "buy_trigger_price": round(buy_trigger, 2),
                "sell_trigger_price": round(target_price, 2),
                "stop_loss_price": round(stop_loss, 2),
                "take_profit_price": round(target_price, 2),
                "valid_from": today.isoformat(),
                "valid_until": valid_until.isoformat(),
                "expiry_action": "REVIEW",
                "conditions": [
                    {
                        "type": "PRICE_BELOW",
                        "price": round(buy_trigger, 2),
                        "action": "BUY",
                        "quantity": quantity,
                    },
                    {
                        "type": "PRICE_ABOVE",
                        "price": round(target_price, 2),
                        "action": "SELL",
                        "quantity": quantity,
                    },
                ],
            }
        )

    data_gaps = list(state.get("data_gaps", []) or [])
    action = "BUY" if monitored_stocks else ("WAIT" if stock_pool else "NO_TRADE")
    reasoning = build_decision_reason(action, monitored_stocks, data_gaps)
    trade_plan = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "monitored_stocks": monitored_stocks,
        "position_sizing_rationale": (
            f"单只仓位不超过 {max_single_pct:.0f}%，总仓位不超过 {max_total_pct:.0f}%；"
            "数量按 A 股 100 股整数倍取整。"
        ),
    }
    confidence = 0.72 if monitored_stocks else 0.35
    if data_gaps:
        confidence = max(confidence - 0.15, 0.2)

    return {
        "final_decision": {
            "action": action,
            "reasoning": reasoning,
        },
        "trade_plan": trade_plan,
        "alternative_scenarios": [
            {
                "scenario": "大盘突发利空或流动性急剧收缩",
                "action": "暂停新买入，已触发订单按止损规则处理。",
            },
            {
                "scenario": "关键数据源不可用",
                "action": "交易计划保持观察状态，待数据恢复后重新生成。",
            },
        ],
        "manager_confidence": round(confidence, 2),
    }


def select_purchase_candidates(
    stock_pool: list[dict[str, Any]],
    judge_rulings: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not stock_pool:
        return []
    allowed = {"STRONG_BUY", "BUY"}
    rulings = {
        str(item.get("symbol", "")): item
        for item in (judge_rulings or [])
        if item.get("symbol")
    }
    selected = [
        item
        for item in stock_pool
        if rulings.get(str(item.get("symbol", "")), {}).get("ruling") in allowed
    ]
    if selected:
        return selected[:5]
    return [
        item
        for item in sorted(
            stock_pool,
            key=lambda row: float(row.get("information_score") or 0),
            reverse=True,
        )
        if float(item.get("information_score") or 0) >= 70
    ][:3]


def build_decision_reason(
    action: str,
    monitored_stocks: list[dict[str, Any]],
    data_gaps: list[str],
) -> str:
    if action == "BUY":
        suffix = "；但存在数据缺口，需降仓执行。" if data_gaps else "。"
        return f"裁判和风控后仍有 {len(monitored_stocks)} 个标的满足价格触发式买入条件{suffix}"
    if action == "WAIT":
        return "已有候选股票，但缺少足够价格、裁决或仓位条件，先观察不落交易计划。"
    return "没有可执行候选股票，不生成自动购买计划。"


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
