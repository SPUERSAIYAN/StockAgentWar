from __future__ import annotations

import json
import re
from typing import Any

from agents.information_agent import create_chat_model, invoke_text, prompt_vars
from agents.prompt_loader import PROMPTS_DIR, load_agent_prompt
from agents.trace_logger import (
    log_agent_error,
    log_agent_messages,
    log_agent_output,
    log_agent_start,
)
from schemas.state import AgentRuntimeConfig, MarketDecisionState


ALLOWED_PROVIDER_GROUPS = (
    "us_equity",
    "china_equity",
    "macro",
    "prediction_markets",
    "crypto",
    "web_search",
)
ALLOWED_PROVIDER_GROUP_SET = set(ALLOWED_PROVIDER_GROUPS)
DATA_SOURCES_PROMPT_FILE = "data_sources.md"


class QuestionPlanningAgent:
    """LLM planner that selects provider groups before data collection."""

    def __init__(self, config: AgentRuntimeConfig):
        self.config = config
        self.prompt_file = require_prompt_file(config)
        self.model_config = require_model_config(config)
        self.prompt = load_agent_prompt(self.prompt_file)
        self.data_sources_reference = (PROMPTS_DIR / DATA_SOURCES_PROMPT_FILE).read_text(
            encoding="utf-8"
        )

    def __call__(self, state: MarketDecisionState) -> dict[str, Any]:
        agent_name = self.config.get("name") or "question_planning"
        log_agent_start(agent_name, state, {"role": self.config.get("role")})

        variables = {
            **prompt_vars(state),
            "metadata": json.dumps(state.get("metadata", {}), ensure_ascii=False, indent=2, default=str),
            "data_sources": self.data_sources_reference,
        }
        system_content, user_content = self.prompt.render(variables)
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        log_agent_messages(agent_name, self.model_config, messages)

        try:
            raw_content = invoke_text(create_chat_model(self.model_config), messages)
            parsed = parse_planner_json(raw_content)
            plan = normalize_question_plan(parsed)
        except Exception as exc:
            log_agent_error(agent_name, exc)
            raise

        report = render_question_plan_report(plan)
        log_agent_output(agent_name, "question_plan_report", report)
        return {
            "question_understanding": plan["question_understanding"],
            "provider_selection": plan["provider_selection"],
            "question_plan_report": report,
            "metadata": {
                **dict(state.get("metadata", {}) or {}),
                "question_planning": {
                    "prompt": f"prompts/{self.prompt_file}",
                    "data_sources_prompt": f"prompts/{DATA_SOURCES_PROMPT_FILE}",
                    "model": self.model_config,
                },
            },
        }


def require_prompt_file(config: AgentRuntimeConfig) -> str:
    prompt_file = str(config.get("prompt_file") or "").strip()
    if not prompt_file:
        raise ValueError("QuestionPlanningAgent requires `prompt_file` in its config.")
    return prompt_file


def require_model_config(config: AgentRuntimeConfig) -> dict[str, Any]:
    model_config = dict(config.get("model", {}) or {})
    if not model_config:
        raise ValueError("QuestionPlanningAgent requires `model` in its config.")
    if not model_config.get("provider"):
        raise ValueError("QuestionPlanningAgent model config requires `provider`.")
    return model_config


def parse_planner_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise ValueError("empty question planning response")
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
        raise ValueError("question planning response must be a JSON object")
    return parsed


def normalize_question_plan(plan: dict[str, Any]) -> dict[str, Any]:
    understanding = normalize_question_understanding(plan.get("question_understanding"))
    provider_selection = normalize_provider_selection(plan.get("provider_selection"))
    return {
        "question_understanding": understanding,
        "provider_selection": provider_selection,
    }


def normalize_question_understanding(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("question planning JSON requires `question_understanding`.")
    return {
        "rewritten_question": str(value.get("rewritten_question") or "").strip(),
        "core_intent": str(value.get("core_intent") or "").strip(),
        "market_scope": str(value.get("market_scope") or "").strip(),
        "time_window": str(value.get("time_window") or value.get("primary_time_window") or "").strip(),
        "candidate_scope": str(value.get("candidate_scope") or "").strip(),
        "sector_terms": normalize_text_terms(value.get("sector_terms")),
    }


def normalize_provider_selection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("question planning JSON requires `provider_selection`.")

    selected_groups = normalize_group_list(value.get("selected_groups"), "selected_groups")
    if not selected_groups:
        raise ValueError("provider_selection.selected_groups must include at least one provider group.")

    raw_providers = value.get("providers", {})
    if raw_providers is None:
        raw_providers = {}
    if not isinstance(raw_providers, dict):
        raise ValueError("provider_selection.providers must be a JSON object.")
    unknown_provider_keys = sorted(set(str(key) for key in raw_providers) - ALLOWED_PROVIDER_GROUP_SET)
    if unknown_provider_keys:
        raise ValueError(f"Unknown provider group(s): {', '.join(unknown_provider_keys)}")

    rejected_groups = normalize_group_list(value.get("rejected_groups", []), "rejected_groups")
    providers: dict[str, dict[str, Any]] = {}
    for group in ALLOWED_PROVIDER_GROUPS:
        raw_row = raw_providers.get(group, {})
        if raw_row is None:
            raw_row = {}
        if not isinstance(raw_row, dict):
            raise ValueError(f"provider_selection.providers.{group} must be a JSON object.")
        providers[group] = {
            "enabled": group in selected_groups,
            "reason": str(raw_row.get("reason") or default_provider_reason(group, group in selected_groups)).strip(),
        }

    return {
        "selected_groups": selected_groups,
        "providers": providers,
        "rejected_groups": [group for group in ALLOWED_PROVIDER_GROUPS if group not in selected_groups],
        "basis": {
            "source": "question_planning_llm",
            "llm_rejected_groups": rejected_groups,
        },
    }


def normalize_group_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"provider_selection.{field_name} must be a list.")
    groups: list[str] = []
    for item in value:
        group = str(item.get("provider_group") if isinstance(item, dict) else item).strip()
        if group not in ALLOWED_PROVIDER_GROUP_SET:
            raise ValueError(f"Unknown provider group in {field_name}: {group}")
        if group not in groups:
            groups.append(group)
    return groups


def normalize_text_terms(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = re.split(r"[,，、;；\n]", value)
    elif isinstance(value, list):
        values = value
    else:
        return []
    terms: list[str] = []
    for item in values:
        term = str(item).strip()
        if term and term not in terms:
            terms.append(term)
    return terms


def default_provider_reason(group: str, enabled: bool) -> str:
    action = "Selected" if enabled else "Rejected"
    return f"{action} by QuestionPlanningAgent."


def render_question_plan_report(plan: dict[str, Any]) -> str:
    understanding = plan["question_understanding"]
    selection = plan["provider_selection"]
    lines = [
        "# 问题理解与数据源规划",
        "",
        "## 问题理解",
        "",
        f"- 改写问题：{understanding.get('rewritten_question', '')}",
        f"- 核心意图：{understanding.get('core_intent', '')}",
        f"- 市场范围：{understanding.get('market_scope', '')}",
        f"- 时间窗口：{understanding.get('time_window', '')}",
        f"- 候选范围：{understanding.get('candidate_scope', '')}",
        f"- 板块/概念词：{', '.join(understanding.get('sector_terms', [])) or '无'}",
        "",
        "## 数据源选择",
        "",
        f"- 启用数据源：{', '.join(selection.get('selected_groups', []))}",
        "",
        "| Provider group | Status | Reason |",
        "|---|---|---|",
    ]
    providers = dict(selection.get("providers", {}) or {})
    for group in ALLOWED_PROVIDER_GROUPS:
        row = dict(providers.get(group, {}) or {})
        status = "enabled" if row.get("enabled") else "disabled"
        lines.append(f"| {group} | {status} | {row.get('reason', '')} |")
    return "\n".join(lines)
