from __future__ import annotations

from schemas.state import AgentRuntimeConfig, MarketDecisionState

from agents.skill_agent import run_prompt_agent


class JudgeAgent:
    def __init__(self, config: AgentRuntimeConfig):
        self.config = config

    def __call__(self, state: MarketDecisionState) -> dict[str, str]:
        return run_prompt_agent(
            config=self.config,
            state=state,
            output_key="judge_decision",
            system_prompt=(
                "你是股票市场裁判 Agent。你需要综合信息分析、多头观点和空头观点，"
                "给出稳健、可执行、带风险控制意识的候选股票决策。"
            ),
            user_prompt=(
                "任务：{task}\n\n"
                "信息分析报告：\n{info_report}\n\n"
                "多头观点：\n{bull_case}\n\n"
                "空头观点：\n{bear_case}\n\n"
                "请输出：\n"
                "1. 候选股票表格：股票、方向、优先级、核心理由、主要风险、观察信号\n"
                "2. 最终裁判结论\n"
                "3. 需要风控 Agent 重点检查的问题\n"
                "4. 下一步需要补充的数据"
            ),
        )
