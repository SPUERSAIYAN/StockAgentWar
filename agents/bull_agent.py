from __future__ import annotations

from schemas.state import AgentRuntimeConfig, MarketDecisionState

from agents.prompt_loader import load_agent_prompt
from agents.information_agent import run_prompt_agent


class BullAgent:
    def __init__(self, config: AgentRuntimeConfig):
        self.config = config
        self.prompt = load_agent_prompt("bull_agent.md")

    def __call__(self, state: MarketDecisionState) -> dict[str, str]:
        return run_prompt_agent(
            config=self.config,
            state=state,
            output_key="bull_case",
            prompt_template=self.prompt,
        )

