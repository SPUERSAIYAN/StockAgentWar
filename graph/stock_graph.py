from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.bear_agent import BearAgent
from agents.bull_agent import BullAgent
from agents.judge_agent import JudgeAgent
from agents.risk_agent import RiskAgent
from agents.skill_agent import MarketInformationSkillAgent
from schemas.state import AgentRuntimeConfig, MarketDecisionState


DEFAULT_AGENT_CONFIGS: dict[str, AgentRuntimeConfig] = {
    "information": {
        "name": "information",
        "role": "信息分析 Agent",
        "model": {"provider": "mock", "model": "mock-information", "temperature": 0.2},
    },
    "bull": {
        "name": "bull",
        "role": "多头辩手 Agent",
        "model": {"provider": "mock", "model": "mock-bull", "temperature": 0.5},
    },
    "bear": {
        "name": "bear",
        "role": "空头辩手 Agent",
        "model": {"provider": "mock", "model": "mock-bear", "temperature": 0.5},
    },
    "judge": {
        "name": "judge",
        "role": "裁判 Agent",
        "model": {"provider": "mock", "model": "mock-judge", "temperature": 0.1},
    },
    "risk": {
        "name": "risk",
        "role": "风控 Agent",
        "model": {"provider": "mock", "model": "mock-risk", "temperature": 0.1},
    },
}


def build_stock_graph(
    *,
    agent_configs: dict[str, AgentRuntimeConfig] | None = None,
    information_agent: Any | None = None,
) -> Any:
    configs = agent_configs or DEFAULT_AGENT_CONFIGS

    builder = StateGraph(MarketDecisionState)
    builder.add_node(
        "information_analysis",
        information_agent or MarketInformationSkillAgent(configs["information"]),
    )
    builder.add_node("bull_debate", BullAgent(configs["bull"]))
    builder.add_node("bear_debate", BearAgent(configs["bear"]))
    builder.add_node("judge_decision", JudgeAgent(configs["judge"]))
    builder.add_node("risk_review", RiskAgent(configs["risk"]))
    builder.add_node("format_output", format_output)

    builder.add_edge(START, "information_analysis")
    builder.add_edge("information_analysis", "bull_debate")
    builder.add_edge("information_analysis", "bear_debate")
    builder.add_edge(["bull_debate", "bear_debate"], "judge_decision")
    builder.add_edge("judge_decision", "risk_review")
    builder.add_edge("risk_review", "format_output")
    builder.add_edge("format_output", END)

    return builder.compile()


def format_output(state: MarketDecisionState) -> dict[str, str]:
    final_output = state.get("risk_report") or state.get("judge_decision") or "未生成候选股票结果。"
    return {"final_output": final_output}
