from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.bear_agent import BearAgent
from agents.bull_agent import BullAgent
from agents.information_agent import InformationCollectionAgent
from agents.judge_agent import JudgeAgent
from agents.portfolio_manager_agent import PortfolioManagerAgent
from agents.question_planning_agent import QuestionPlanningAgent
from agents.risk_agent import RiskAgent
from graph.decision_nodes import (
    PortfolioDecisionNode,
    format_final_output,
    save_trade_plan,
    structure_bear_cases,
    structure_bull_cases,
    structure_judge_rulings,
)
from graph.stock_graph import DEFAULT_AGENT_CONFIGS
from schemas.a_share_state import AShareAutoPurchaseState
from schemas.state import AgentRuntimeConfig


DEFAULT_A_SHARE_AGENT_CONFIGS: dict[str, AgentRuntimeConfig] = {
    **{key: dict(value) for key, value in DEFAULT_AGENT_CONFIGS.items()},
    "portfolio_manager": {
        "name": "portfolio_manager",
        "role": "总经理 Agent",
        "model": {"provider": "mock", "model": "mock-portfolio-manager", "temperature": 0.1},
        "position_sizing": {
            "max_single_position_pct": 20,
            "max_total_exposure_pct": 80,
            "cash_reserve_min_pct": 20,
        },
        "risk_control": {
            "max_drawdown_pct": 10,
            "stop_loss_pct": 8,
            "take_profit_pct": 20,
        },
    },
}


def build_a_share_auto_trade_graph(
    *,
    agent_configs: dict[str, AgentRuntimeConfig] | None = None,
    information_agent: Any | None = None,
) -> Any:
    configs = merge_agent_configs(agent_configs)

    builder = StateGraph(AShareAutoPurchaseState)
    builder.add_node("question_planning", QuestionPlanningAgent(configs["question_planning"]))
    builder.add_node(
        "information_analysis",
        information_agent or InformationCollectionAgent(configs["information"]),
    )
    builder.add_node("bull_debate", BullAgent(configs["bull"]))
    builder.add_node("bear_debate", BearAgent(configs["bear"]))
    builder.add_node("bull_cases", structure_bull_cases)
    builder.add_node("bear_cases", structure_bear_cases)
    builder.add_node("judge_decision", JudgeAgent(configs["judge"]))
    builder.add_node("judge_rulings", structure_judge_rulings)
    builder.add_node("risk_review", RiskAgent(configs["risk"]))
    builder.add_node("portfolio_manager", PortfolioManagerAgent(configs["portfolio_manager"]))
    builder.add_node("portfolio_decision", PortfolioDecisionNode(configs["portfolio_manager"]))
    builder.add_node("save_trade_plan", save_trade_plan)
    builder.add_node("final_output", format_final_output)

    builder.add_edge(START, "question_planning")
    builder.add_edge("question_planning", "information_analysis")
    builder.add_edge("information_analysis", "bull_debate")
    builder.add_edge("information_analysis", "bear_debate")
    builder.add_edge("bull_debate", "bull_cases")
    builder.add_edge("bear_debate", "bear_cases")
    builder.add_edge(["bull_cases", "bear_cases"], "judge_decision")
    builder.add_edge("judge_decision", "judge_rulings")
    builder.add_edge("judge_rulings", "risk_review")
    builder.add_edge("risk_review", "portfolio_manager")
    builder.add_edge("portfolio_manager", "portfolio_decision")
    builder.add_edge("portfolio_decision", "save_trade_plan")
    builder.add_edge("save_trade_plan", "final_output")
    builder.add_edge("final_output", END)

    return builder.compile()


def merge_agent_configs(
    agent_configs: dict[str, AgentRuntimeConfig] | None,
) -> dict[str, AgentRuntimeConfig]:
    configs = {key: dict(value) for key, value in DEFAULT_A_SHARE_AGENT_CONFIGS.items()}
    for name, override in (agent_configs or {}).items():
        base = dict(configs.get(name, {"name": name, "role": name}))
        base.update(override)
        if "model" in override and isinstance(override["model"], dict):
            model = dict(configs.get(name, {}).get("model", {}))
            model.update(override["model"])
            base["model"] = model
        configs[name] = base
    return configs
