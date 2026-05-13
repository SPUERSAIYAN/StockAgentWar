from __future__ import annotations

import json
import re
from typing import Any

from agents.information_agent import create_chat_model, invoke_text, prompt_vars
from agents.prompt_loader import load_agent_prompt
from agents.trace_logger import (
    log_agent_error,
    log_agent_messages,
    log_agent_output,
    log_agent_start,
)
from schemas.state import AgentRuntimeConfig, MarketDecisionState, ModelConfig


ALLOWED_PROVIDER_GROUPS = {
    "china_equity",
    "us_equity",
    "macro",
    "prediction_markets",
    "crypto",
    "web_search",
}

DEFAULT_PLANNER_MODEL: ModelConfig = {
    "provider": "openrouter",
    "model": "qwen/qwen3.5-plus-20260420",
    "temperature": 0.1,
    "api_key_env": "OPENROUTER_API_KEY",
    "site_url": "http://localhost",
    "app_title": "multi-Agent-Inv",
}


class QuestionPlanningAgent:
    """LLM planner that rewrites the user question and selects data-source groups."""

    def __init__(self, config: AgentRuntimeConfig | None = None):
        self.config = config or {}
        self.prompt = load_agent_prompt("question_planning_agent.md")
        self.model_config = build_planner_model_config(self.config)

    def __call__(self, state: MarketDecisionState) -> dict[str, Any]:
        agent_name = self.config.get("name") or "question_planning"
        log_agent_start(agent_name, state, {"role": "question planning"})

        variables = {
            **prompt_vars(state),
            "metadata": json.dumps(state.get("metadata", {}), ensure_ascii=False, indent=2, default=str),
        }
        system_content, user_content = self.prompt.render(variables)
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        log_agent_messages(agent_name, self.model_config, messages)

        parse_error: str | None = None
        try:
            model = create_chat_model(self.model_config)
            raw_content = invoke_text(model, messages)
            parsed = parse_planner_json(raw_content)
        except Exception as exc:
            log_agent_error(agent_name, exc)
            raw_content = ""
            parsed = fallback_question_plan(state)
            parse_error = f"{type(exc).__name__}: {exc}"

        plan = sanitize_question_plan(parsed, state)
        if parse_error:
            plan.setdefault("metadata", {})["planner_parse_error"] = parse_error

        report = render_question_plan_report(plan)
        log_agent_output(agent_name, "question_plan_report", report)
        return {
            "question_understanding": plan["question_understanding"],
            "signal_plan": plan["signal_plan"],
            "question_plan_report": report,
            "metadata": {
                **dict(state.get("metadata", {})),
                "question_planning": {
                    "prompt": "prompts/question_planning_agent.md",
                    "model": self.model_config,
                    "parse_error": parse_error,
                },
            },
        }


def build_planner_model_config(config: AgentRuntimeConfig) -> ModelConfig:
    source_model = dict(config.get("model", {}) or {})
    if source_model.get("provider") == "mock":
        return {"provider": "mock", "model": "mock-question-planning", "temperature": 0.0}
    passthrough = {
        key: value
        for key, value in source_model.items()
        if key in {"api_key_env", "base_url", "site_url", "app_title", "default_headers", "kwargs"}
    }
    return {
        **DEFAULT_PLANNER_MODEL,
        **passthrough,
        "provider": "openrouter",
        "temperature": float(source_model.get("temperature", DEFAULT_PLANNER_MODEL["temperature"])),
    }


def parse_planner_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise ValueError("empty planner response")
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("planner response must be a JSON object")
    return parsed


def sanitize_question_plan(plan: dict[str, Any], state: MarketDecisionState) -> dict[str, Any]:
    fallback = fallback_question_plan(state)
    understanding = {
        **fallback["question_understanding"],
        **dict(plan.get("question_understanding", {}) or {}),
    }
    raw_signal_plan = dict(plan.get("signal_plan", {}) or {})
    selected_groups = normalize_provider_groups(raw_signal_plan.get("selected_provider_groups"))
    rejected_groups = normalize_rejected_groups(raw_signal_plan.get("rejected_provider_groups"))

    if is_a_share_planning_context(state, understanding):
        selected_groups = ["china_equity", "macro"]
        rejected_groups = [
            {"provider_group": group, "reason": "A-share planning defaults to China equity data plus macro risk proxies."}
            for group in sorted(ALLOWED_PROVIDER_GROUPS - set(selected_groups))
        ]
    elif not selected_groups:
        selected_groups = fallback["signal_plan"]["selected_provider_groups"]
        rejected_groups = fallback["signal_plan"]["rejected_provider_groups"]

    invalid_groups = [
        str(group)
        for group in raw_signal_plan.get("selected_provider_groups", []) or []
        if str(group) not in ALLOWED_PROVIDER_GROUPS
    ]
    if invalid_groups:
        rejected_groups.extend(
            {"provider_group": group, "reason": "Rejected because this project cannot call that provider group."}
            for group in invalid_groups
        )

    selected_signals = normalize_selected_signals(raw_signal_plan.get("selected_signals"), selected_groups)
    if not selected_signals:
        selected_signals = fallback_signals_for_groups(selected_groups)

    data_needed = raw_signal_plan.get("data_needed_by_information_agent")
    if not isinstance(data_needed, list) or not data_needed:
        data_needed = [item["description"] for item in selected_signals]

    return {
        "question_understanding": {
            "rewritten_question": str(understanding.get("rewritten_question") or fallback["question_understanding"]["rewritten_question"]),
            "core_intent": str(understanding.get("core_intent") or fallback["question_understanding"]["core_intent"]),
            "market_scope": str(understanding.get("market_scope") or fallback["question_understanding"]["market_scope"]),
            "primary_time_window": str(understanding.get("primary_time_window") or fallback["question_understanding"]["primary_time_window"]),
            "secondary_time_window": str(understanding.get("secondary_time_window") or fallback["question_understanding"]["secondary_time_window"]),
            "candidate_scope": str(understanding.get("candidate_scope") or fallback["question_understanding"]["candidate_scope"]),
            "risk_notes": normalize_text_list(understanding.get("risk_notes")),
        },
        "signal_plan": {
            "selected_provider_groups": selected_groups,
            "selected_signals": selected_signals,
            "rejected_provider_groups": dedupe_rejected_groups(rejected_groups, selected_groups),
            "data_needed_by_information_agent": normalize_text_list(data_needed),
        },
    }


def fallback_question_plan(state: MarketDecisionState) -> dict[str, Any]:
    task = state.get("task", "").strip()
    is_a_share = is_a_share_planning_context(state, {})
    short_term = is_short_term_question(task)
    if is_a_share:
        selected_groups = ["china_equity", "macro"]
        rewritten = "A股市场极短期具有上涨潜力的个股/板块识别" if short_term else "A股市场候选股票与板块机会识别"
        core_intent = "寻找当前市场定价中存在正向预期差的方向"
        market_scope = "China A-share"
        candidate_scope = "A-share candidate discovery when explicit symbols are absent"
    else:
        selected_groups = ["us_equity", "macro"]
        rewritten = task or "Global equity candidate assessment"
        core_intent = "Assess tradable upside/downside using structured market data"
        market_scope = "US/global listed assets"
        candidate_scope = "User-supplied symbols"

    return {
        "question_understanding": {
            "rewritten_question": rewritten,
            "core_intent": core_intent,
            "market_scope": market_scope,
            "primary_time_window": "1-5 trading days" if short_term else "3-12 months",
            "secondary_time_window": "1-3 months trend confirmation" if short_term else "1-3 years context",
            "candidate_scope": candidate_scope,
            "risk_notes": ["Research support only; do not frame as personalized investment advice."],
        },
        "signal_plan": {
            "selected_provider_groups": selected_groups,
            "selected_signals": fallback_signals_for_groups(selected_groups),
            "rejected_provider_groups": [
                {"provider_group": group, "reason": "Not needed for this question's market scope or time window."}
                for group in sorted(ALLOWED_PROVIDER_GROUPS - set(selected_groups))
            ],
            "data_needed_by_information_agent": [
                item["description"] for item in fallback_signals_for_groups(selected_groups)
            ],
        },
    }


def normalize_provider_groups(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    groups: list[str] = []
    for item in value:
        group = str(item.get("provider_group") if isinstance(item, dict) else item).strip()
        if group in ALLOWED_PROVIDER_GROUPS and group not in groups:
            groups.append(group)
    return groups


def normalize_rejected_groups(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            group = str(item.get("provider_group") or item.get("group") or "").strip()
            reason = str(item.get("reason") or "Rejected by planner.").strip()
        else:
            group = str(item).strip()
            reason = "Rejected by planner."
        if group:
            rows.append({"provider_group": group, "reason": reason})
    return rows


def normalize_selected_signals(value: Any, selected_groups: list[str]) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    selected = set(selected_groups)
    for index, item in enumerate(value, 1):
        if not isinstance(item, dict):
            continue
        group = str(item.get("provider_group") or "").strip()
        if group not in selected:
            continue
        rows.append(
            {
                "id": str(item.get("id") or item.get("signal") or f"{group}.signal_{index}"),
                "provider_group": group,
                "description": str(item.get("description") or item.get("data_needed") or "Planner-selected signal."),
                "reason": str(item.get("reason") or item.get("why") or "Selected by question planner."),
            }
        )
    return rows


def fallback_signals_for_groups(groups: list[str]) -> list[dict[str, str]]:
    menu = {
        "china_equity": [
            ("china.candidate_discovery", "A-share candidate discovery, realtime quotes, valuation, turnover, volume ratio and amount.", "Needed to identify tradable A-share candidates."),
            ("china.kline_and_intraday", "Daily/minute K-lines, intraday points, transactions and order book when enabled.", "Needed to separate short-term momentum from chasing risk."),
        ],
        "macro": [
            ("macro.risk_pricing", "USDCNY, VIX, broad risk proxies, rates and positioning where enabled.", "Needed to cross-check market risk appetite."),
        ],
        "us_equity": [
            ("equity.price_options", "Price history, weekly trend, realized volatility, options and EDGAR where available.", "Needed for listed US/global symbols."),
        ],
        "prediction_markets": [
            ("prediction.event_probabilities", "Kalshi/Polymarket real-money event probabilities.", "Needed when event probabilities affect the thesis."),
        ],
        "crypto": [
            ("crypto.risk_appetite", "BTC/ETH spot and derivatives.", "Needed for crypto assets or risk-appetite proxy checks."),
        ],
        "web_search": [
            ("web.structured_gaps", "Structured market-data pages not covered by providers.", "Needed only for explicit provider gaps."),
        ],
    }
    rows: list[dict[str, str]] = []
    for group in groups:
        for signal_id, description, reason in menu.get(group, []):
            rows.append(
                {
                    "id": signal_id,
                    "provider_group": group,
                    "description": description,
                    "reason": reason,
                }
            )
    return rows


def dedupe_rejected_groups(rows: list[dict[str, str]], selected_groups: list[str]) -> list[dict[str, str]]:
    selected = set(selected_groups)
    seen: set[str] = set()
    output: list[dict[str, str]] = []
    for item in rows:
        group = str(item.get("provider_group") or "").strip()
        if not group or group in selected or group in seen:
            continue
        seen.add(group)
        output.append({"provider_group": group, "reason": str(item.get("reason") or "Rejected.")})
    return output


def normalize_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def is_a_share_planning_context(state: MarketDecisionState, understanding: dict[str, Any]) -> bool:
    task = state.get("task", "").casefold()
    metadata = dict(state.get("metadata", {}) or {})
    if str(metadata.get("ui_mode", "")).startswith("a_share"):
        return True
    symbols = [str(item.get("symbol", "")) for item in state.get("candidates", []) if item.get("symbol")]
    if any(re.fullmatch(r"(SH|SZ)?\d{6}", symbol.strip().upper()) or re.fullmatch(r"\d{6}\.(SH|SZ)", symbol.strip().upper()) for symbol in symbols):
        return True
    market_scope = str(understanding.get("market_scope", "")).casefold()
    a_share_tokens = (
        "a股",
        "a 股",
        "大a",
        "沪深",
        "中国股市",
        "中国股票",
        "china a-share",
        "a-share",
        "ashare",
    )
    stock_pick_tokens = ("哪只股票", "哪一只", "买哪只", "短线", "明天")
    return any(token in task or token in market_scope for token in a_share_tokens) or (
        any(token in task for token in stock_pick_tokens) and not symbols
    )


def is_short_term_question(task: str) -> bool:
    lowered = task.casefold()
    return any(
        token in lowered
        for token in (
            "明天",
            " tomorrow",
            "next day",
            "短线",
            "短期",
            "1-5",
            "几天",
            "next few days",
        )
    )


def render_question_plan_report(plan: dict[str, Any]) -> str:
    understanding = plan["question_understanding"]
    signal_plan = plan["signal_plan"]
    lines = [
        "# 问题理解与信号规划",
        "",
        "## 问题理解",
        "",
        f"- 改写问题：{understanding.get('rewritten_question', '')}",
        f"- 核心意图：{understanding.get('core_intent', '')}",
        f"- 市场范围：{understanding.get('market_scope', '')}",
        f"- 主时间窗口：{understanding.get('primary_time_window', '')}",
        f"- 辅助时间窗口：{understanding.get('secondary_time_window', '')}",
        f"- 候选范围：{understanding.get('candidate_scope', '')}",
        "",
        "## 规划信号",
        "",
        f"- 启用数据源：{', '.join(signal_plan.get('selected_provider_groups', []))}",
        "",
        "| Signal | Provider | Why |",
        "|---|---|---|",
    ]
    for item in signal_plan.get("selected_signals", []):
        lines.append(
            "| {signal} | {provider} | {reason} |".format(
                signal=item.get("id", ""),
                provider=item.get("provider_group", ""),
                reason=item.get("reason") or item.get("description", ""),
            )
        )
    rejected = signal_plan.get("rejected_provider_groups", [])
    if rejected:
        lines.extend(["", "## 拒绝的数据源", "", "| Provider | Reason |", "|---|---|"])
        for item in rejected:
            lines.append(f"| {item.get('provider_group', '')} | {item.get('reason', '')} |")
    return "\n".join(lines)
