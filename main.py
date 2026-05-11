from __future__ import annotations

import argparse
import warnings
from pathlib import Path

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
from schemas.state import AgentRuntimeConfig, StockCandidate


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LangGraph stock decision system.")
    parser.add_argument("--task", default="筛选候选股票", help="决策任务")
    parser.add_argument(
        "--symbols",
        default="",
        help="逗号分隔的股票代码，例如 AAPL,MSFT,NVDA",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="可选 YAML 配置文件，用于覆盖每个 agent 的模型配置",
    )
    args = parser.parse_args()

    agent_configs = load_agent_configs(args.config)
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


def parse_symbols(raw: str) -> list[StockCandidate]:
    symbols = [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]
    return [{"symbol": symbol} for symbol in symbols]


if __name__ == "__main__":
    main()
