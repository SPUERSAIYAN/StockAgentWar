from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from datetime import datetime
from typing import Any


_PRINT_LOCK = threading.Lock()


def trace_enabled() -> bool:
    value = os.getenv("AGENT_TRACE", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def agent_trace_enabled() -> bool:
    value = os.getenv("AGENT_TRACE_AGENTS", "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


def task_build_trace_enabled() -> bool:
    value = os.getenv("AGENT_TRACE_TASK_BUILD", "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


def traceback_enabled() -> bool:
    value = os.getenv("AGENT_TRACE_TRACEBACK", "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


def max_chars() -> int:
    raw = os.getenv("AGENT_TRACE_MAX_CHARS", "4000")
    try:
        return max(int(raw), 200)
    except ValueError:
        return 4000


def log_agent_start(agent_name: str, state: dict[str, Any], extra: dict[str, Any] | None = None) -> None:
    if not agent_trace_enabled():
        return
    sections = [("STATE INPUT", summarize_state(state))]
    if extra:
        sections.append(("CONTEXT", extra))
    log_block(agent_name, "START", sections)


def log_agent_messages(
    agent_name: str,
    model_config: dict[str, Any],
    messages: list[dict[str, str]],
) -> None:
    if not agent_trace_enabled():
        return
    safe_model_config = redact_model_config(model_config)
    sections: list[tuple[str, Any]] = [("MODEL", safe_model_config)]
    for index, message in enumerate(messages, start=1):
        role = message.get("role", "message").upper()
        sections.append((f"LLM INPUT {index} ({role})", message.get("content", "")))
    log_block(agent_name, "LLM CALL", sections)


def log_agent_output(agent_name: str, output_key: str, content: Any) -> None:
    if not agent_trace_enabled():
        return
    log_block(agent_name, "OUTPUT", [(output_key, content)])


def log_agent_error(agent_name: str, error: BaseException) -> None:
    log_block(
        agent_name,
        "ERROR",
        [
            (
                "EXCEPTION",
                {
                    "type": type(error).__name__,
                    "message": str(error),
                },
            )
        ],
    )


def log_trace(agent_name: str, event: str, payload: Any) -> None:
    if event not in {"COLLECTOR SKIP"}:
        return
    log_block(agent_name, event, [(event, payload)])


def log_data_source_start(label: str, context: dict[str, Any] | None = None) -> None:
    if not trace_enabled() or (label.startswith("task_build.") and not task_build_trace_enabled()):
        return
    message = f"DATA SOURCE START label={label}"
    if context:
        message += format_context_suffix(context)
    log_line(message)


def log_data_source_success(label: str, elapsed_ms: int, value: Any) -> None:
    if not trace_enabled() or (label.startswith("task_build.") and not task_build_trace_enabled()):
        return
    summary = summarize_data_source_value(value)
    log_line(f"DATA SOURCE OK label={label} elapsed_ms={elapsed_ms} {format_flat_summary(summary)}")


def log_data_source_error(label: str, elapsed_ms: int, error: BaseException) -> None:
    if not trace_enabled():
        return
    message = (
        f"DATA SOURCE FAIL label={label} elapsed_ms={elapsed_ms} "
        f"error={type(error).__name__}: {str(error)}"
    )
    log_line(message)
    if traceback_enabled():
        log_block(
            f"data_source:{label}",
            "TRACEBACK",
            [("TRACEBACK", "".join(traceback.format_exception(type(error), error, error.__traceback__)))],
        )


def log_data_source_plan(
    *,
    task_count: int,
    symbols: list[str],
    tasks: list[str],
    task_build_errors: dict[str, str] | None = None,
) -> None:
    if not trace_enabled():
        return
    preview = ", ".join(tasks[:12])
    if len(tasks) > 12:
        preview += f", ... +{len(tasks) - 12} more"
    symbol_text = ",".join(symbols) if symbols else "(none)"
    log_line(f"DATA SOURCE PLAN count={task_count} symbols={symbol_text} tasks=[{preview}]")
    for label, error in (task_build_errors or {}).items():
        log_line(f"DATA SOURCE BUILD FAIL label={label} error={error}")


def log_collector_summary(
    *,
    enabled: bool,
    timeout_seconds: Any,
    max_workers: Any,
    yahoo_max_workers: Any = None,
    providers: dict[str, Any],
) -> None:
    if not trace_enabled():
        return
    enabled_groups = [
        name
        for name, config in providers.items()
        if not isinstance(config, dict) or config.get("enabled", True) is not False
    ]
    yahoo_text = (
        f" yahoo_max_workers={yahoo_max_workers}"
        if yahoo_max_workers is not None
        else ""
    )
    log_line(
        "COLLECTOR "
        f"enabled={enabled} timeout_seconds={timeout_seconds} "
        f"max_workers={max_workers}{yahoo_text} providers={','.join(enabled_groups)}"
    )


def log_block(agent_name: str, event: str, sections: list[tuple[str, Any]]) -> None:
    if not trace_enabled():
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "=" * 88
    header = f"[{timestamp}] AGENT TRACE | {agent_name} | {event}"
    parts = [line, header, line]
    for title, value in sections:
        parts.append(f"\n--- {title} ---")
        parts.append(format_value(value))
    parts.append(line)
    text = "\n".join(parts)

    with _PRINT_LOCK:
        print(text, file=sys.stderr, flush=True)


def log_line(message: str) -> None:
    if not trace_enabled():
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _PRINT_LOCK:
        print(f"[{timestamp}] {message}", file=sys.stderr, flush=True)


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    simple_keys = (
        "task",
        "candidates",
        "question_understanding",
        "question_plan_report",
        "information_workflow",
        "provider_selection",
        "signal_reasoning",
        "metadata",
        "errors",
    )
    for key in simple_keys:
        if key in state:
            summary[key] = state[key]

    text_keys = ("info_report", "bull_case", "bear_case", "judge_decision", "risk_report", "final_output")
    handoffs: dict[str, dict[str, Any]] = {}
    for key in text_keys:
        value = state.get(key)
        if isinstance(value, str) and value:
            handoffs[key] = {
                "chars": len(value),
                "preview": truncate(value, 900),
            }
    if handoffs:
        summary["agent_handoffs"] = handoffs

    if "raw_market_data" in state:
        raw = state.get("raw_market_data") or {}
        if isinstance(raw, dict):
            summary["raw_market_data"] = {
                "collection_status": raw.get("collection_status"),
                "source_count": raw.get("source_count"),
                "error_count": raw.get("error_count"),
                "sources": list(dict(raw.get("sources", {}) or {}).keys()),
                "errors": list(dict(raw.get("errors", {}) or {}).keys()),
            }
    for key in (
        "stock_pool",
        "sector_summary",
        "bull_cases",
        "bear_cases",
        "judge_rulings",
        "trade_plan",
        "final_decision",
    ):
        if key in state:
            value = state.get(key)
            if isinstance(value, list):
                summary[key] = {"count": len(value), "preview": value[:3]}
            elif isinstance(value, dict):
                summary[key] = value
    return summary


def redact_model_config(config: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in dict(config or {}).items():
        lowered = key.lower()
        if "key" in lowered or "token" in lowered or "secret" in lowered:
            redacted[key] = "***"
        elif isinstance(value, dict):
            redacted[key] = redact_model_config(value)
        else:
            redacted[key] = value
    return redacted


def format_value(value: Any) -> str:
    if isinstance(value, str):
        return truncate(value, max_chars())
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        text = str(value)
    return truncate(text, max_chars())


def summarize_data_source_value(value: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "type": value.__class__.__name__,
    }
    if isinstance(value, (list, tuple)):
        summary["item_count"] = len(value)
        summary["item_type"] = value[0].__class__.__name__ if value else ""
        summary["preview_count"] = min(len(value), 3)
        return summary
    if isinstance(value, dict):
        summary["keys"] = list(value.keys())[:30]
        summary["key_count"] = len(value)
        return summary
    for attr in (
        "provider_id",
        "symbol",
        "raw_symbol",
        "ticker",
        "currency",
        "date",
        "curve_kind",
        "query",
        "fetched_at",
    ):
        if hasattr(value, attr):
            summary[attr] = getattr(value, attr)
    for attr in ("bars", "points", "strikes", "recent_form4s", "snippets"):
        if hasattr(value, attr):
            try:
                summary[f"{attr}_count"] = len(list(getattr(value, attr) or ()))
            except TypeError:
                summary[f"{attr}_count"] = "unknown"
    return summary


def format_context_suffix(context: dict[str, Any]) -> str:
    pieces = []
    for key in ("group", "symbol", "data_kind"):
        value = context.get(key)
        if value:
            pieces.append(f"{key}={value}")
    return " " + " ".join(pieces) if pieces else ""


def format_flat_summary(summary: dict[str, Any]) -> str:
    keep_keys = (
        "type",
        "provider_id",
        "symbol",
        "raw_symbol",
        "ticker",
        "currency",
        "date",
        "curve_kind",
        "item_count",
        "item_type",
        "bars_count",
        "points_count",
        "strikes_count",
        "recent_form4s_count",
        "snippets_count",
        "key_count",
    )
    pieces = []
    for key in keep_keys:
        if key in summary and summary[key] not in (None, ""):
            pieces.append(f"{key}={summary[key]}")
    return " ".join(pieces)


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"{text[:limit]}\n...TRUNCATED {omitted} chars..."
