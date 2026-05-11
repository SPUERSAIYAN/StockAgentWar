from __future__ import annotations

from schemas.state import AgentRuntimeConfig, MarketDecisionState

from agents.skill_agent import run_prompt_agent


class BearAgent:
    def __init__(self, config: AgentRuntimeConfig):
        self.config = config

    def __call__(self, state: MarketDecisionState) -> dict[str, str]:
        return run_prompt_agent(
            config=self.config,
            state=state,
            output_key="bear_case",
            system_prompt=(
                "你是空头辩手 Agent。你必须基于信息分析报告提出回避、减仓或做空风险，"
                "强调估值、基本面、技术面和宏观风险。"
            ),
            user_prompt=(
                "任务：{task}\n"
                "候选股票：\n{candidates}\n\n"
                "信息分析报告：\n{info_report}\n\n"
                "请站在空头视角输出：\n"
                "1. 风险最大的候选股票\n"
                "2. 下跌或跑输逻辑\n"
                "3. 关键证据\n"
                "4. 空头观点失效条件"
            ),
        )
