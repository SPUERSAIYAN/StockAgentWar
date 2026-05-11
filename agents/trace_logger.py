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


def max_chars() -> int:
    raw = os.getenv("AGENT_TRACE_MAX_CHARS", "4000")
    try:
        return max(int(raw), 200)
    except ValueError:
        return 4000


def log_agent_start(agent_name: str, state: dict[str, Any], extra: dict[str, Any] | None = None) -> None:
    sections = [("STATE INPUT", summarize_state(state))]
    if extra:
        sections.append(("CONTEXT", extra))
    log_block(agent_name, "START", sections)


def log_agent_messages(
    agent_name: str,
    model_config: dict[str, Any],
    messages: list[dict[str, str]],
) -> None:
    safe_model_config = redact_model_config(model_config)
    sections: list[tuple[str, Any]] = [("MODEL", safe_model_config)]
    for index, message in enumerate(messages, start=1):
        role = message.get("role", "message").upper()
        sections.append((f"LLM INPUT {index} ({role})", message.get("content", "")))
    log_block(agent_name, "LLM CALL", sections)


def log_agent_output(agent_name: str, output_key: str, content: Any) -> None:
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
    log_block(agent_name, event, [(event, payload)])


def log_data_source_start(label: str, context: dict[str, Any] | None = None) -> None:
    sections: list[tuple[str, Any]] = []
    if context:
        sections.append(("CONTEXT", context))
    log_block(f"data_source:{label}", "START", sections)


def log_data_source_success(label: str, elapsed_ms: int, value: Any) -> None:
    log_block(
        f"data_source:{label}",
        "SUCCESS",
        [
            ("ELAPSED_MS", elapsed_ms),
            ("RESULT SUMMARY", summarize_data_source_value(value)),
        ],
    )


def log_data_source_error(label: str, elapsed_ms: int, error: BaseException) -> None:
    log_block(
        f"data_source:{label}",
        "ERROR",
        [
            ("ELAPSED_MS", elapsed_ms),
            (
                "EXCEPTION",
                {
                    "type": type(error).__name__,
                    "message": str(error),
                },
            ),
            ("TRACEBACK", "".join(traceback.format_exception(type(error), error, error.__traceback__))),
        ],
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


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    simple_keys = (
        "task",
        "candidates",
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
        summary["preview"] = value[:3]
        return summary
    if isinstance(value, dict):
        summary["keys"] = list(value.keys())[:30]
        summary["preview"] = value
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
    summary["preview"] = value
    return summary


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"{text[:limit]}\n...TRUNCATED {omitted} chars..."
