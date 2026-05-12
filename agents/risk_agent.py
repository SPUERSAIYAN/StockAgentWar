from __future__ import annotations

from typing import Any

from schemas.state import AgentRuntimeConfig

from agents.prompt_loader import load_agent_prompt
from agents.information_agent import run_prompt_agent


class RiskAgent:
    def __init__(self, config: AgentRuntimeConfig):
        self.config = config
        self.prompt = load_agent_prompt("risk_agent.md")

    def __call__(self, state: dict[str, Any]) -> dict[str, str]:
        return run_prompt_agent(
            config=self.config,
            state=state,
            output_key="risk_report",
            prompt_template=self.prompt,
        )
