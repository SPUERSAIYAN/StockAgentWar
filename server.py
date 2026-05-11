from __future__ import annotations

import json
import os
import time
import warnings
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
except Exception:
    LangChainPendingDeprecationWarning = PendingDeprecationWarning

warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)
warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects`.*",
    module=r"langgraph\.cache\.base.*",
)

from graph.stock_graph import DEFAULT_AGENT_CONFIGS, build_stock_graph
from main import load_agent_configs, parse_symbols


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"

load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(title="Stock Decision System")


class DecisionRequest(BaseModel):
    task: str = Field(default="筛选未来 1-3 个月的候选股票")
    symbols: str = Field(default="AAPL,MSFT,NVDA")
    mode: Literal["openrouter", "mock"] = "openrouter"
    config_path: str = Field(default="config.yaml")


STAGES: dict[str, dict[str, str]] = {
    "information_analysis": {
        "id": "information_analysis",
        "agent": "信息分析",
        "title": "市场信息汇总",
        "output_key": "info_report",
    },
    "bull_debate": {
        "id": "bull_debate",
        "agent": "多头",
        "title": "上涨逻辑",
        "output_key": "bull_case",
    },
    "bear_debate": {
        "id": "bear_debate",
        "agent": "空头",
        "title": "风险反驳",
        "output_key": "bear_case",
    },
    "judge_decision": {
        "id": "judge_decision",
        "agent": "裁判",
        "title": "综合裁决",
        "output_key": "judge_decision",
    },
    "risk_review": {
        "id": "risk_review",
        "agent": "风控",
        "title": "风险复核",
        "output_key": "risk_report",
    },
}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "config_exists": DEFAULT_CONFIG_PATH.exists(),
        "openrouter_key_ready": bool(os.getenv("OPENROUTER_API_KEY")),
        "stages": list(STAGES.values()),
    }


@app.post("/api/decide/stream")
def decide_stream(request: DecisionRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_decision(request),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def stream_decision(request: DecisionRequest):
    started_at = time.perf_counter()
    state: dict[str, Any] = {}
    completed: set[str] = set()

    yield event(
        "start",
        {
            "task": request.task,
            "symbols": request.symbols,
            "mode": request.mode,
            "stages": list(STAGES.values()),
        },
    )
    yield stage_status("information_analysis", "running", started_at)

    try:
        agent_configs = resolve_agent_configs(request)
        graph = build_stock_graph(agent_configs=agent_configs)
        inputs = {
            "task": request.task,
            "candidates": parse_symbols(request.symbols),
            "agent_configs": agent_configs,
            "metadata": {"ui_mode": request.mode},
        }

        for update in graph.stream(inputs, stream_mode="updates"):
            for node, node_update in update.items():
                if not isinstance(node_update, dict):
                    continue
                state.update(node_update)

                if node in STAGES:
                    completed.add(node)
                    output_key = STAGES[node]["output_key"]
                    yield event(
                        "stage",
                        {
                            "node": node,
                            "status": "done",
                            "elapsed_ms": elapsed_ms(started_at),
                            "output_key": output_key,
                            "content": node_update.get(output_key, ""),
                        },
                    )
                    yield from emit_next_statuses(node, completed, started_at)

                if node == "format_output":
                    yield event(
                        "complete",
                        {
                            "elapsed_ms": elapsed_ms(started_at),
                            "final_output": node_update.get("final_output", ""),
                            "state": public_state(state),
                        },
                    )
    except Exception as exc:
        yield event(
            "error",
            {
                "elapsed_ms": elapsed_ms(started_at),
                "message": str(exc),
                "hint": "检查 OPENROUTER_API_KEY、config.yaml 模型名和网络代理设置。",
            },
        )


def resolve_agent_configs(request: DecisionRequest):
    if request.mode == "mock":
        return {key: dict(value) for key, value in DEFAULT_AGENT_CONFIGS.items()}

    config_path = Path(request.config_path)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    return load_agent_configs(config_path)


def emit_next_statuses(node: str, completed: set[str], started_at: float):
    if node == "information_analysis":
        yield stage_status("bull_debate", "running", started_at)
        yield stage_status("bear_debate", "running", started_at)
    elif {"bull_debate", "bear_debate"}.issubset(completed) and "judge_decision" not in completed:
        yield stage_status("judge_decision", "running", started_at)
    elif node == "judge_decision":
        yield stage_status("risk_review", "running", started_at)


def stage_status(node: str, status: str, started_at: float) -> str:
    return event(
        "stage_status",
        {
            "node": node,
            "status": status,
            "elapsed_ms": elapsed_ms(started_at),
        },
    )


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    keys = ["info_report", "bull_case", "bear_case", "judge_decision", "risk_report", "final_output"]
    return {key: state[key] for key in keys if key in state}


def elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def event(event_type: str, payload: dict[str, Any]) -> str:
    return json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n"


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
