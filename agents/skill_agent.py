from __future__ import annotations

import importlib
import json
import math
import os
import re
import sys
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from schemas.state import AgentRuntimeConfig, MarketDecisionState, ModelConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_SKILL_DIR = PROJECT_ROOT / "external" / "Market-Information-Skill"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class ChatModel(Protocol):
    def invoke(self, messages: list[dict[str, str]]) -> Any:
        ...


@dataclass(slots=True)
class MockChatModel:
    name: str

    def invoke(self, messages: list[dict[str, str]]) -> str:
        user_message = messages[-1]["content"] if messages else ""
        model_name = self.name.lower()
        if "information" in model_name or "info" in model_name or "信息分析" in self.name:
            return mock_information_report(user_message)
        if "bull" in model_name or "多头" in self.name:
            return mock_bull_case(user_message)
        if "bear" in model_name or "空头" in self.name:
            return mock_bear_case(user_message)
        if "judge" in model_name or "裁判" in self.name:
            return mock_judge_decision(user_message)
        if "risk" in model_name or "风控" in self.name:
            return mock_risk_report(user_message)
        return f"[{self.name}] mock response\n\n{user_message[:500]}"


class MarketInformationSkillAgent:
    """Information analysis node backed by digital_oracle providers."""

    def __init__(self, config: AgentRuntimeConfig):
        self.config = config
        self.model = create_chat_model(config.get("model", {}))

    def __call__(self, state: MarketDecisionState) -> dict[str, Any]:
        collected = collect_market_information(state, self.config)
        if collected:
            report = build_collected_market_report(state, self.config, self.model, collected)
            return {
                "info_report": report,
                "raw_market_data": collected,
                "metadata": {
                    **state.get("metadata", {}),
                    "information_source": "external/Market-Information-Skill",
                },
            }

        prompt = (
            f"任务：{state.get('task', '筛选候选股票')}\n"
            f"候选输入：{format_candidates(state.get('candidates', []))}\n\n"
            "请输出：\n"
            "1. 关键市场背景\n"
            "2. 每只股票的核心利好/利空事实\n"
            "3. 数据缺口和谨慎假设\n"
            "4. 可进入辩论阶段的候选股票清单"
        )
        content = invoke_text(
            self.model,
            [
                {
                    "role": "system",
                    "content": (
                        "你是股票市场信息分析 Agent。你负责汇总行情、基本面、新闻、"
                        "资金流、技术面和宏观信息，形成后续辩论可引用的事实报告。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        return {"info_report": content}


def run_prompt_agent(
    *,
    config: AgentRuntimeConfig,
    state: MarketDecisionState,
    system_prompt: str,
    user_prompt: str,
    output_key: str,
) -> dict[str, str]:
    model = create_chat_model(config.get("model", {}))
    content = invoke_text(
        model,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt.format(**prompt_vars(state))},
        ],
    )
    return {output_key: content}


def create_chat_model(config: ModelConfig) -> ChatModel:
    provider = config.get("provider", "mock").lower()
    if provider == "mock":
        return MockChatModel(config.get("model", "mock"))
    if provider == "openai":
        return create_openai_model(config)
    if provider == "openrouter":
        return create_openrouter_model(config)
    if provider == "custom":
        return load_custom_model(config)
    raise ValueError(f"Unsupported model provider: {provider}")


def invoke_text(model: ChatModel, messages: list[dict[str, str]]) -> str:
    response = model.invoke(messages)
    if isinstance(response, str):
        return response
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "\n".join(content_part_to_text(part) for part in content)
    return str(content)


def create_openai_model(config: ModelConfig) -> ChatModel:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI provider requires `pip install -r requirements.txt`.") from exc

    kwargs = dict(config.get("kwargs", {}))
    api_key_env = config.get("api_key_env")
    if api_key_env and os.getenv(api_key_env):
        kwargs["api_key"] = os.getenv(api_key_env)
    return ChatOpenAI(
        model=config.get("model", "gpt-4o-mini"),
        temperature=float(config.get("temperature", 0.2)),
        **kwargs,
    )


def create_openrouter_model(config: ModelConfig) -> ChatModel:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("OpenRouter provider requires `pip install -r requirements.txt`.") from exc

    kwargs = dict(config.get("kwargs", {}))
    api_key_env = config.get("api_key_env", "OPENROUTER_API_KEY")
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing OpenRouter API key. Set ${api_key_env} first.")

    default_headers = dict(config.get("default_headers", {}))
    site_url = config.get("site_url") or os.getenv("OPENROUTER_SITE_URL")
    app_title = config.get("app_title") or os.getenv("OPENROUTER_APP_TITLE")
    if site_url:
        default_headers["HTTP-Referer"] = site_url
    if app_title:
        default_headers["X-OpenRouter-Title"] = app_title

    if default_headers:
        kwargs["default_headers"] = default_headers

    return ChatOpenAI(
        model=config.get("model", "openai/gpt-5.2"),
        temperature=float(config.get("temperature", 0.2)),
        api_key=api_key,
        base_url=config.get("base_url") or os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL),
        **kwargs,
    )


def load_custom_model(config: ModelConfig) -> ChatModel:
    import_path = config.get("import_path")
    if not import_path:
        raise ValueError("Custom model provider requires `import_path`.")
    factory = import_from_path(import_path)
    return factory(**dict(config.get("kwargs", {})))


def import_from_path(import_path: str) -> Any:
    module_name, _, attr = import_path.partition(":")
    if not module_name or not attr:
        raise ValueError("Import path must use `module.path:attribute` format.")
    module = importlib.import_module(module_name)
    return getattr(module, attr)
def prompt_vars(state: MarketDecisionState) -> dict[str, str]:
    return {
        "task": state.get("task", "筛选候选股票"),
        "candidates": format_candidates(state.get("candidates", [])),
        "info_report": state.get("info_report", "暂无信息分析报告。"),
        "bull_case": state.get("bull_case", "暂无多头观点。"),
        "bear_case": state.get("bear_case", "暂无空头观点。"),
        "judge_decision": state.get("judge_decision", "暂无裁判结论。"),
    }


def format_candidates(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "未提供明确候选股票，可由信息分析 Agent 基于任务自行提出。"
    rows = []
    for item in candidates:
        rows.append(" / ".join(str(item.get(key, "")) for key in ("symbol", "name", "market") if item.get(key)))
    return "\n".join(f"- {row}" for row in rows)


def content_part_to_text(part: Any) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, dict):
        return str(part.get("text") or part.get("content") or part)
    return str(part)


def collect_market_information(
    state: MarketDecisionState,
    config: AgentRuntimeConfig,
) -> dict[str, Any] | None:
    collector_config = dict(config.get("collector", {}))
    if collector_config.get("enabled", False) is False:
        return None
    if not (EXTERNAL_SKILL_DIR / "digital_oracle").exists():
        return None

    ensure_external_skill_path()

    try:
        from digital_oracle import (
            EdgarInsiderQuery,
            EdgarProvider,
            FearGreedProvider,
            OptionsChainQuery,
            PriceHistoryQuery,
            TencentFinanceProvider,
            TencentStockMetricsQuery,
            USTreasuryProvider,
            YahooPriceProvider,
            YFinanceProvider,
            gather,
        )
    except Exception as exc:
        return {
            "collection_status": "unavailable",
            "generated_at": now_iso(),
            "sources": {},
            "errors": {"digital_oracle_import": f"{type(exc).__name__}: {exc}"},
        }

    symbols = extract_candidate_symbols(state)
    if not symbols:
        return {
            "collection_status": "empty",
            "generated_at": now_iso(),
            "sources": {},
            "errors": {"symbols": "未提供候选股票代码，无法调用市场数据 provider。"},
        }

    price_limit = int(collector_config.get("price_history_limit", 90))
    timeout_seconds = float(collector_config.get("timeout_seconds", 35))
    max_workers = int(collector_config.get("max_workers", 12))
    include_macro = bool(collector_config.get("include_macro", True))
    include_options = bool(collector_config.get("include_options", True))
    include_edgar = bool(collector_config.get("include_edgar", True))
    include_a_share_metrics = bool(collector_config.get("include_a_share_metrics", True))
    edgar_user_email = (
        collector_config.get("edgar_user_email")
        or os.getenv("EDGAR_USER_EMAIL")
        or "market-information-agent@example.com"
    )

    tasks: dict[str, Any] = {}
    for symbol in symbols:
        if is_a_share_symbol(symbol):
            if include_a_share_metrics:
                tasks[f"equity.{symbol}.tencent_metrics"] = (
                    lambda s=symbol: TencentFinanceProvider().get_stock_metrics(
                        TencentStockMetricsQuery(symbols=(s,))
                    )
                )
            continue

        yahoo_symbol = to_yahoo_symbol(symbol)
        tasks[f"equity.{symbol}.price_daily"] = (
            lambda s=yahoo_symbol: YahooPriceProvider().get_history(
                PriceHistoryQuery(symbol=s, interval="d", limit=price_limit)
            )
        )
        tasks[f"equity.{symbol}.price_weekly"] = (
            lambda s=yahoo_symbol: YahooPriceProvider().get_history(
                PriceHistoryQuery(symbol=s, interval="w", limit=52)
            )
        )
        if include_options and is_plain_us_equity(yahoo_symbol):
            tasks[f"equity.{symbol}.options_nearest"] = (
                lambda s=yahoo_symbol: YFinanceProvider().get_chain(
                    OptionsChainQuery(ticker=s)
                )
            )
        if include_edgar and is_plain_us_equity(yahoo_symbol):
            tasks[f"equity.{symbol}.edgar_form4"] = (
                lambda s=yahoo_symbol: EdgarProvider(
                    user_email=edgar_user_email
                ).get_insider_transactions(EdgarInsiderQuery(ticker=s, limit=8))
            )

    if include_macro:
        macro_symbols = tuple(collector_config.get("macro_symbols", ("SPY", "QQQ", "^VIX", "GC=F", "USDCNY=X")))
        tasks["macro.yield_curve"] = lambda: USTreasuryProvider().latest_yield_curve()
        tasks["macro.fear_greed"] = lambda: FearGreedProvider().get_index()
        for macro_symbol in macro_symbols:
            tasks[f"macro.price.{macro_symbol}"] = (
                lambda s=macro_symbol: YahooPriceProvider().get_history(
                    PriceHistoryQuery(symbol=s, interval="d", limit=60)
                )
            )

    gathered = gather(
        tasks,
        max_workers=max_workers,
        timeout_seconds=timeout_seconds,
        fail_fast=False,
    )
    return summarize_gathered_market_data(
        task=state.get("task", ""),
        symbols=symbols,
        results=gathered.results,
        errors=gathered.errors,
    )


def ensure_external_skill_path() -> None:
    external_path = str(EXTERNAL_SKILL_DIR)
    if EXTERNAL_SKILL_DIR.exists() and external_path not in sys.path:
        sys.path.insert(0, external_path)


def extract_candidate_symbols(state: MarketDecisionState) -> list[str]:
    seen: set[str] = set()
    symbols: list[str] = []
    for candidate in state.get("candidates", []):
        symbol = str(candidate.get("symbol", "")).strip()
        if not symbol:
            continue
        normalized = symbol.upper()
        if normalized not in seen:
            seen.add(normalized)
            symbols.append(normalized)
    return symbols


def summarize_gathered_market_data(
    *,
    task: str,
    symbols: list[str],
    results: dict[str, Any],
    errors: dict[str, BaseException],
) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    for label, value in results.items():
        sources[label] = summarize_provider_value(value)

    rendered_errors = {
        label: f"{type(exc).__name__}: {exc}" for label, exc in errors.items()
    }
    if results and rendered_errors:
        status = "partial"
    elif results:
        status = "ok"
    else:
        status = "failed"

    return {
        "collection_status": status,
        "generated_at": now_iso(),
        "task": task,
        "symbols": symbols,
        "source_count": len(results),
        "error_count": len(rendered_errors),
        "sources": sources,
        "errors": rendered_errors,
    }


def summarize_provider_value(value: Any) -> Any:
    class_name = value.__class__.__name__
    if hasattr(value, "bars"):
        return summarize_price_history(value)
    if class_name == "OptionsChain":
        return summarize_options_chain(value)
    if class_name == "EdgarInsiderSummary":
        return summarize_edgar_insider(value)
    if class_name == "YieldCurveSnapshot":
        return summarize_yield_curve(value)
    if class_name == "FearGreedSnapshot":
        return to_jsonable(value)
    if isinstance(value, (list, tuple)) and value and value[0].__class__.__name__ == "TencentStockMetrics":
        return [summarize_tencent_metrics(item) for item in value]
    return to_jsonable(value)


def summarize_price_history(history: Any) -> dict[str, Any]:
    bars = list(getattr(history, "bars", ()) or ())
    latest = bars[-1] if bars else None
    earliest = bars[0] if bars else None
    closes = [float(bar.close) for bar in bars if getattr(bar, "close", None) is not None]
    volumes = [
        float(bar.volume)
        for bar in bars[-20:]
        if getattr(bar, "volume", None) not in (None, 0)
    ]
    return {
        "provider": getattr(history, "provider_id", ""),
        "symbol": getattr(history, "symbol", ""),
        "raw_symbol": getattr(history, "raw_symbol", ""),
        "interval": getattr(history, "interval", ""),
        "bar_count": len(bars),
        "earliest": to_jsonable(earliest),
        "latest": to_jsonable(latest),
        "return_total_pct": percent_change(
            getattr(earliest, "close", None),
            getattr(latest, "close", None),
        ),
        "return_20_bar_pct": percent_change(
            closes[-21] if len(closes) >= 21 else None,
            closes[-1] if closes else None,
        ),
        "high_20": max((float(getattr(bar, "high", 0)) for bar in bars[-20:]), default=None),
        "low_20": min((float(getattr(bar, "low", 0)) for bar in bars[-20:]), default=None),
        "avg_volume_20": safe_average(volumes),
        "realized_vol_20_annualized": realized_volatility(closes[-21:]),
    }


def summarize_options_chain(chain: Any) -> dict[str, Any]:
    return {
        "ticker": getattr(chain, "ticker", ""),
        "expiration": getattr(chain, "expiration", ""),
        "underlying_price": getattr(chain, "underlying_price", None),
        "atm_strike": chain.atm_strike,
        "atm_iv": chain.atm_iv,
        "implied_move": chain.implied_move(),
        "put_call_volume_ratio": chain.put_call_volume_ratio,
        "put_call_oi_ratio": chain.put_call_oi_ratio,
        "total_volume": chain.total_volume,
        "total_open_interest": chain.total_open_interest,
        "max_pain": chain.max_pain(),
    }


def summarize_edgar_insider(summary: Any) -> dict[str, Any]:
    return {
        "ticker": getattr(summary, "ticker", ""),
        "company_name": getattr(summary, "company_name", ""),
        "cik": getattr(summary, "cik", ""),
        "total_form4_count": getattr(summary, "total_form4_count", 0),
        "recent_form4s": [
            to_jsonable(item) for item in list(getattr(summary, "recent_form4s", ()) or ())[:5]
        ],
    }


def summarize_yield_curve(snapshot: Any) -> dict[str, Any]:
    tenors = {point.tenor: point.value for point in getattr(snapshot, "points", ())}
    return {
        "date": getattr(snapshot, "date", ""),
        "curve_kind": getattr(snapshot, "curve_kind", ""),
        "tenors": tenors,
        "spread_10y_2y": snapshot.spread("10Y", "2Y"),
        "spread_10y_3m": snapshot.spread("10Y", "3M"),
    }


def summarize_tencent_metrics(metrics: Any) -> dict[str, Any]:
    data = to_jsonable(metrics)
    keep_keys = (
        "symbol",
        "name",
        "price",
        "change_pct",
        "turnover_rate",
        "volume_ratio",
        "pe",
        "pb",
        "float_market_cap_cny_100m",
        "total_market_cap_cny_100m",
        "amount_cny_10k",
    )
    return {key: data.get(key) for key in keep_keys if key in data}


def build_collected_market_report(
    state: MarketDecisionState,
    config: AgentRuntimeConfig,
    model: ChatModel,
    collected: dict[str, Any],
) -> str:
    if isinstance(model, MockChatModel):
        return render_deterministic_report(
            task=state.get("task", "筛选候选股票"),
            candidates=state.get("candidates", []),
            data=collected,
        )

    data_json = json.dumps(collected, ensure_ascii=False, indent=2, default=str)
    max_chars = int(config.get("collector", {}).get("llm_context_chars", 24000))
    if len(data_json) > max_chars:
        data_json = data_json[:max_chars] + "\n...TRUNCATED..."

    prompt = (
        f"任务：{state.get('task', '筛选候选股票')}\n"
        f"候选股票：\n{format_candidates(state.get('candidates', []))}\n\n"
        "以下是 market-information-skill 采集到的结构化市场数据。"
        "请只基于这些数据做信息整理，不要编造未出现的数据。\n\n"
        f"```json\n{data_json}\n```\n\n"
        "请输出 Markdown 报告，结构必须包含：\n"
        "1. 数据覆盖摘要：成功来源、失败来源、时间戳\n"
        "2. 市场背景：指数、波动率、利率、风险偏好\n"
        "3. 个股信息卡：价格趋势、成交量、期权/情绪、内部人/估值数据\n"
        "4. 明确利好事实与利空事实\n"
        "5. 数据缺口：哪些关键数据未获取，后续 agent 应谨慎处理\n"
        "6. 可进入多空辩论的候选股票清单"
    )
    try:
        return invoke_text(
            model,
            [
                {
                    "role": "system",
                    "content": (
                        "你是股票市场信息收集 Agent。你的职责是把 provider 拉到的结构化交易数据"
                        "整理成事实报告，供多头、空头和裁判 agent 使用。坚持事实和缺口标注。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:
        fallback = render_deterministic_report(
            task=state.get("task", "筛选候选股票"),
            candidates=state.get("candidates", []),
            data=collected,
        )
        return f"{fallback}\n\n## 信息报告 LLM 生成失败\n\n- {type(exc).__name__}: {exc}"


def render_deterministic_report(
    *,
    task: str,
    candidates: list[dict[str, Any]],
    data: dict[str, Any],
) -> str:
    lines = [
        "## 信息收集报告",
        "",
        f"- 任务：{task}",
        f"- 候选股票：{format_candidates(candidates)}",
        f"- 采集状态：{data.get('collection_status', 'unknown')}",
        f"- 采集时间：{data.get('generated_at', '')}",
        f"- 成功来源数：{data.get('source_count', 0)}",
        f"- 失败来源数：{data.get('error_count', 0)}",
        "",
        "### 成功数据源",
    ]
    sources = data.get("sources", {})
    if sources:
        for label, value in sources.items():
            lines.append(f"- `{label}`：{compact_json(value, 420)}")
    else:
        lines.append("- 暂无成功数据源。")

    errors = data.get("errors", {})
    lines.extend(["", "### 数据缺口"])
    if errors:
        for label, message in errors.items():
            lines.append(f"- `{label}`：{message}")
    else:
        lines.append("- 暂无 provider 错误。")

    lines.extend(
        [
            "",
            "### 给后续 Agent 的使用提示",
            "- 多头/空头辩论应优先引用成功数据源中的价格、波动率、估值、资金情绪和利率信号。",
            "- 对失败来源涉及的结论必须降级为假设，不应当作为确定性证据。",
        ]
    )
    return "\n".join(lines)


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def compact_json(value: Any, max_chars: int) -> str:
    text = json.dumps(to_jsonable(value), ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def percent_change(start: Any, end: Any) -> float | None:
    try:
        start_float = float(start)
        end_float = float(end)
    except (TypeError, ValueError):
        return None
    if start_float == 0:
        return None
    return round((end_float / start_float - 1) * 100, 4)


def realized_volatility(closes: list[float]) -> float | None:
    if len(closes) < 3:
        return None
    returns = []
    for previous, current in zip(closes, closes[1:]):
        if previous <= 0 or current <= 0:
            continue
        returns.append(math.log(current / previous))
    if len(returns) < 2:
        return None
    mean_return = sum(returns) / len(returns)
    variance = sum((item - mean_return) ** 2 for item in returns) / (len(returns) - 1)
    return round(math.sqrt(variance) * math.sqrt(252), 6)


def safe_average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def to_yahoo_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if normalized.endswith(".US"):
        return normalized[:-3]
    return normalized


def is_plain_us_equity(symbol: str) -> bool:
    normalized = symbol.strip().upper()
    if any(marker in normalized for marker in ("=", "^", ".", "-")):
        return False
    return bool(re.fullmatch(r"[A-Z]{1,5}", normalized))


def is_a_share_symbol(symbol: str) -> bool:
    normalized = symbol.strip().upper()
    return bool(
        re.fullmatch(r"(SH|SZ)?\d{6}", normalized)
        or re.fullmatch(r"\d{6}\.(SH|SZ)", normalized)
    )


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def mock_information_report(user_message: str) -> str:
    return (
        "## 信息分析报告\n\n"
        "- 当前运行在 mock 模式，尚未调用真实行情/新闻/财报 API。\n"
        "- 这里是接入 `external/Market-Information-Skill` 的位置，用于汇总市场信息。\n"
        "- 后续多头、空头、裁判、风控 agent 都会基于本报告继续推理。\n\n"
        f"### 任务摘录\n{user_message[:600]}"
    )


def mock_bull_case(user_message: str) -> str:
    return (
        "## 多头观点\n\n"
        "- 优先关注盈利预期上修、资金流入、技术形态转强的标的。\n"
        "- 看多触发条件：放量突破关键阻力、行业催化落地、财报超预期。\n"
        "- 失效条件：跌破关键支撑、市场风险偏好下降、核心假设被证伪。\n\n"
        f"### 输入摘录\n{user_message[:500]}"
    )


def mock_bear_case(user_message: str) -> str:
    return (
        "## 空头观点\n\n"
        "- 警惕估值过高、利好兑现、盈利质量下降和流动性退潮。\n"
        "- 回避触发条件：高位缩量、跌破均线、负面新闻或宏观压力升温。\n"
        "- 失效条件：重新放量走强、业绩超预期、风险事件解除。\n\n"
        f"### 输入摘录\n{user_message[:500]}"
    )


def mock_judge_decision(user_message: str) -> str:
    return (
        "## 裁判决策\n\n"
        "| 股票 | 方向 | 优先级 | 核心理由 | 主要风险 | 观察信号 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| 待接入真实数据 | WATCH | 中 | mock 模式仅验证多 agent 协作链路 | 缺少实时数据 | 接入信息分析 skill 后再排序 |\n\n"
        "结论：当前框架已完成信息分析、多空辩论和裁判决策。真实交易前需要接入数据、风控阈值和人工复核。\n\n"
        f"### 输入摘录\n{user_message[:700]}"
    )


def mock_risk_report(user_message: str) -> str:
    return (
        "## 风控复核\n\n"
        "| 股票 | 方向 | 优先级 | 建议仓位 | 止损/失效条件 | 主要风险 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| 待接入真实数据 | WATCH | 中 | 0%-5% | 数据补齐前不进入实盘 | 缺少实时行情、成交量、财报和新闻验证 |\n\n"
        "- 单一标的建议设置最大仓位上限，并根据波动率动态调整。\n"
        "- 若候选股票缺少实时数据、成交量或财报验证，应保持 WATCH 而非直接 BUY。\n"
        "- 输出仅用于研究流程验证，不构成投资建议。\n\n"
        f"### 裁判输入摘录\n{user_message[:700]}"
    )
