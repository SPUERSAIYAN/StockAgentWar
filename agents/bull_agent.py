from __future__ import annotations

from schemas.state import AgentRuntimeConfig, MarketDecisionState

from agents.skill_agent import run_prompt_agent


class BullAgent:
    def __init__(self, config: AgentRuntimeConfig):
        self.config = config

    def __call__(self, state: MarketDecisionState) -> dict[str, str]:
        return run_prompt_agent(
            config=self.config,
            state=state,
            output_key="bull_case",
            system_prompt=(
                "你是多头辩手 Agent。你必须基于信息分析报告提出买入或重点观察理由，"
                "强调上涨催化剂、风险收益比和确认信号。"
            ),
            user_prompt=(
                "任务：{task}\n"
                "候选股票：\n{candidates}\n\n"
                "信息分析报告：\n{info_report}\n\n"
                "请站在多头视角输出：\n"
                "1. 最值得看多的候选股票\n"
                "2. 上涨逻辑和触发条件\n"
                "3. 关键证据\n"
                "4. 多头观点失效条件"
            ),
        )
