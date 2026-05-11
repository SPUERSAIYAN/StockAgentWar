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
    api_key_env: str
    base_url: str
    site_url: str
    app_title: str
    import_path: str
    default_headers: dict[str, str]
    kwargs: dict[str, Any]


class AgentRuntimeConfig(TypedDict, total=False):
    name: str
    role: str
    model: ModelConfig
    collector: dict[str, Any]
    prompt_overrides: dict[str, str]


class MarketDecisionState(TypedDict, total=False):
    task: str
    candidates: list[StockCandidate]
    information_workflow: dict[str, Any]
    provider_selection: dict[str, Any]
    signal_reasoning: dict[str, Any]
    raw_market_data: dict[str, Any]
    info_report: str
    bull_case: str
    bear_case: str
    judge_decision: str
    risk_report: str
    final_output: str
    agent_configs: dict[str, AgentRuntimeConfig]
    metadata: dict[str, Any]
    errors: list[str]
