from __future__ import annotations

import argparse
import getpass
import sys
import warnings
from pathlib import Path
from typing import Any

import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

try:
    from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
except Exception:
    LangChainPendingDeprecationWarning = PendingDeprecationWarning

warnings.filterwarnings(
    "ignore",
    category=LangChainPendingDeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects`.*",
    module=r"langgraph\.cache\.base.*",
)

from graph.stock_graph import DEFAULT_AGENT_CONFIGS, build_stock_graph
from graph.a_share_auto_trade_graph import build_a_share_auto_trade_graph
from schemas.state import AgentRuntimeConfig, StockCandidate


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LangGraph stock decision system.")
    parser.add_argument("--task", default="筛选候选股票", help="决策任务")
    parser.add_argument(
        "--mode",
        default="stock_decision",
        choices=("stock_decision", "a_share_daily", "a_share_sector", "a_share_deep"),
        help="运行模式：通用股票决策或 A 股自动购买流程",
    )
    parser.add_argument(
        "--symbols",
        default="",
        help="逗号分隔的股票代码，例如 AAPL,MSFT,NVDA",
    )
    parser.add_argument(
        "--sectors",
        default="",
        help="A 股模式使用，逗号分隔的板块名称，例如 白酒,半导体,新能源",
    )
    parser.add_argument(
        "--risk-tolerance",
        default="moderate",
        choices=("conservative", "moderate", "aggressive"),
        help="A 股模式使用，风险偏好",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=1_000_000,
        help="A 股模式使用，可用资金",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="可选 YAML 配置文件，用于覆盖每个 agent 的模型配置",
    )
    parser.add_argument(
        "--openrouter-api-key",
        default="",
        help="运行时 OpenRouter API Key；未提供时会安全提示输入",
    )
    args = parser.parse_args()

    try:
        agent_configs = load_agent_configs(args.config)
        ensure_runtime_openrouter_api_key(agent_configs, args.openrouter_api_key)
        if args.mode.startswith("a_share_"):
            graph = build_a_share_auto_trade_graph(agent_configs=agent_configs)
            result = graph.invoke(
                {
                    "task": args.task,
                    "candidates": parse_symbols(args.symbols),
                    "scan_scope": {
                        "market": "A_SHARE",
                        "sectors": parse_csv(args.sectors),
                        "exclude_st": True,
                        "exclude_new_days": 60,
                    },
                    "portfolio_context": {
                        "current_positions": [],
                        "available_capital": args.capital,
                        "max_position_pct": 20,
                        "max_drawdown_limit": 10,
                        "risk_tolerance": args.risk_tolerance,
                    },
                    "agent_configs": agent_configs,
                    "metadata": {"mode": args.mode},
                }
            )
        else:
            graph = build_stock_graph(agent_configs=agent_configs)
            result = graph.invoke(
                {
                    "task": args.task,
                    "candidates": parse_symbols(args.symbols),
                    "agent_configs": agent_configs,
                    "metadata": {},
                }
            )
        print(result.get("final_output") or result.get("risk_report") or result.get("judge_decision"))
    except Exception as exc:
        print(f"运行失败：{format_runtime_api_key_error(exc)}", file=sys.stderr)
        raise SystemExit(1) from exc


def load_agent_configs(path: Path | None) -> dict[str, AgentRuntimeConfig]:
    configs: dict[str, AgentRuntimeConfig] = {
        key: dict(value) for key, value in DEFAULT_AGENT_CONFIGS.items()
    }
    if not path:
        return configs

    with path.open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config must be a YAML mapping: {path}")

    overrides = loaded.get("agents", loaded)
    if not isinstance(overrides, dict):
        raise ValueError("Config `agents` must be a mapping.")

    for name, override in overrides.items():
        if not isinstance(override, dict):
            continue
        base = dict(configs.get(name, {"name": name, "role": name}))
        base.update(override)
        if "model" in override and isinstance(override["model"], dict):
            base_model = dict(configs.get(name, {}).get("model", {}))
            base_model.update(override["model"])
            base["model"] = base_model
        configs[name] = base
    return configs


def ensure_runtime_openrouter_api_key(
    configs: dict[str, AgentRuntimeConfig],
    api_key: str,
) -> None:
    if not has_openrouter_model(configs):
        return
    api_key = api_key.strip()
    if not api_key:
        api_key = getpass.getpass("OpenRouter API Key: ").strip()
    if not api_key:
        raise RuntimeError("请提供 OpenRouter API Key。")
    inject_openrouter_api_key(configs, api_key)


def has_openrouter_model(configs: dict[str, AgentRuntimeConfig]) -> bool:
    return any(is_openrouter_config(config) for config in configs.values())


def inject_openrouter_api_key(configs: dict[str, AgentRuntimeConfig], api_key: str) -> None:
    for config in configs.values():
        if not is_openrouter_config(config):
            continue
        model = config.get("model")
        if isinstance(model, dict):
            model["api_key"] = api_key


def is_openrouter_config(config: Any) -> bool:
    if not isinstance(config, dict):
        return False
    model = config.get("model")
    return isinstance(model, dict) and str(model.get("provider", "")).lower() == "openrouter"


def format_runtime_api_key_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "请提供 openrouter api key" in lowered or "missing openrouter api key" in lowered:
        return "请提供 OpenRouter API Key。"
    if "api key" in lowered or "unauthorized" in lowered or "forbidden" in lowered or "401" in lowered or "403" in lowered:
        return f"OpenRouter API Key 无效或已被拒绝，请检查运行时输入的 Key。原始错误：{message}"
    return message


def parse_symbols(raw: str) -> list[StockCandidate]:
    symbols = [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]
    return [{"symbol": symbol} for symbol in symbols]


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


if __name__ == "__main__":
    main()
