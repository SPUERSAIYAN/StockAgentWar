from __future__ import annotations

from typing import Any, Literal, TypedDict


DecisionDirection = Literal["BUY", "WATCH", "AVOID", "SHORT", "NEUTRAL"]


class StockCandidate(TypedDict, total=False):
    symbol: str
    name: str
    market: str
    reason: str
    score: float
    direction: DecisionDirection
    metadata: dict[str, Any]


class ModelConfig(TypedDict, total=False):
    provider: str
    model: str
    temperature: float
    api_key: str
    base_url: str
    site_url: str
    app_title: str
    import_path: str
    default_headers: dict[str, str]
    kwargs: dict[str, Any]


class AgentRuntimeConfig(TypedDict, total=False):
    name: str
    role: str
    prompt_file: str
    model: ModelConfig
    collector: dict[str, Any]
    prompt_overrides: dict[str, str]
    position_sizing: dict[str, Any]
    risk_control: dict[str, Any]
    simulated_initial_capital: float


class MarketDecisionState(TypedDict, total=False):
    task: str
    candidates: list[StockCandidate]
    question_understanding: dict[str, Any]
    question_plan_report: str
    information_workflow: dict[str, Any]
    provider_selection: dict[str, Any]
    signal_reasoning: dict[str, Any]
    raw_market_data: dict[str, Any]
    info_report: str
    bull_case: str
    bear_case: str
    stock_pool: list[dict[str, Any]]
    sector_summary: list[dict[str, Any]]
    confidence_level: float
    data_gaps: list[str]
    macro_context: dict[str, Any]
    bull_cases: list[dict[str, Any]]
    bear_cases: list[dict[str, Any]]
    bull_summary: str
    bear_summary: str
    bull_overall_confidence: float
    bear_overall_confidence: float
    judge_decision: str
    judge_rulings: list[dict[str, Any]]
    judge_report: str
    overall_market_view: str
    risk_report: str
    manager_report: str
    final_decision: dict[str, Any]
    trade_plan: dict[str, Any]
    alternative_scenarios: list[dict[str, Any]]
    manager_confidence: float
    portfolio_context: dict[str, Any]
    final_output: str
    agent_configs: dict[str, AgentRuntimeConfig]
    metadata: dict[str, Any]
    errors: list[str]
