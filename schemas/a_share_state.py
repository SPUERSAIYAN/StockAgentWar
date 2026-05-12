from __future__ import annotations

from typing import Any, Literal, TypedDict

from schemas.state import MarketDecisionState


TradeAction = Literal["BUY", "HOLD", "WAIT", "NO_TRADE"]
JudgeRuling = Literal["STRONG_BUY", "BUY", "WATCH", "AVOID", "STRONG_AVOID"]
CredibilityLevel = Literal["HIGH", "MEDIUM", "LOW"]
ExpiryAction = Literal["SELL", "HOLD", "REVIEW"]


class AShareAutoPurchaseState(MarketDecisionState, total=False):
    stock_pool: list[dict[str, Any]]
    sector_summary: list[dict[str, Any]]
    confidence_level: float
    data_gaps: list[str]

    bull_cases: list[dict[str, Any]]
    bear_cases: list[dict[str, Any]]
    bull_summary: str
    bear_summary: str
    bull_overall_confidence: float
    bear_overall_confidence: float

    judge_rulings: list[dict[str, Any]]
    judge_report: str
    overall_market_view: str

    final_decision: dict[str, Any]
    trade_plan: dict[str, Any]
    alternative_scenarios: list[dict[str, Any]]
    manager_report: str
    manager_confidence: float

    execution_results: list[dict[str, Any]]
    portfolio_context: dict[str, Any]
    macro_context: dict[str, Any]


class TradePlanCondition(TypedDict, total=False):
    type: Literal["PRICE_ABOVE", "PRICE_BELOW", "PRICE_RANGE"]
    price: float
    action: Literal["BUY", "SELL"]
    quantity: int
