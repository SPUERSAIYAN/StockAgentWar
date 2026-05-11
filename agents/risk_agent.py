from __future__ import annotations

from schemas.state import AgentRuntimeConfig, MarketDecisionState

from agents.skill_agent import run_prompt_agent


class RiskAgent:
    def __init__(self, config: AgentRuntimeConfig):
        self.config = config

    def __call__(self, state: MarketDecisionState) -> dict[str, str]:
        return run_prompt_agent(
            config=self.config,
            state=state,
            output_key="risk_report",
            system_prompt=(
                "你是风控 Agent。你负责审查裁判决策是否存在仓位、波动率、流动性、"
                "数据缺口和极端事件风险，并给出最终可执行输出。"
            ),
            user_prompt=(
                "任务：{task}\n\n"
                "候选股票：\n{candidates}\n\n"
                "裁判决策：\n{judge_decision}\n\n"
                "请输出最终候选股票结果，格式为：\n"
                "1. 风控后候选股票表格：股票、方向、优先级、建议仓位、止损/失效条件、主要风险\n"
                "2. 风险复核结论\n"
                "3. 不应进入候选池的标的及原因\n"
                "4. 数据不足时需要暂停交易的条件"
            ),
        )
