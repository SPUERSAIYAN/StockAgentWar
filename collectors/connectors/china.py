from __future__ import annotations

from typing import Any, Callable


TaskMap = dict[str, Callable[[], Any]]


def build_china_equity_tasks(*, symbols: list[str], config: dict[str, Any]) -> TaskMap:
    provider_config = dict(config.get("providers", {}).get("china_equity", {}))
    if provider_config.get("enabled", True) is False:
        return {}

    tasks: TaskMap = {}
    include_tencent = bool(provider_config.get("tencent", config.get("include_a_share_metrics", True)))
    include_mootdx = bool(provider_config.get("mootdx", False))

    if include_tencent:
        from collectors.digital_oracle import TencentBoardQuery, TencentFinanceProvider, TencentStockMetricsQuery

        for symbol in symbols:
            tasks[f"equity.{symbol}.tencent_metrics"] = (
                lambda s=symbol: TencentFinanceProvider().get_stock_metrics(
                    TencentStockMetricsQuery(symbols=(s,))
                )
            )
        if bool(provider_config.get("tencent_index_metrics", True)):
            index_symbols = tuple(provider_config.get("tencent_index_symbols", ("sh000001", "sz399001", "sz399006")))
            tasks["china.tencent.index_metrics"] = (
                lambda s=index_symbols: TencentFinanceProvider().get_index_metrics(s)
            )
        for index, query_config in enumerate(provider_config.get("tencent_board_queries", ()), 1):
            if not isinstance(query_config, dict) or not query_config.get("path"):
                continue
            label = safe_task_label(query_config.get("label", index))
            params = dict(query_config.get("params", {}) or {})
            tasks[f"china.tencent.board.{label}"] = (
                lambda path=str(query_config["path"]), p=params: TencentFinanceProvider().fetch_board_json_like(
                    TencentBoardQuery(path=path, params=p)
                )
            )

    if include_mootdx:
        from collectors.digital_oracle import (
            MootdxBarQuery,
            MootdxCompanyProfileQuery,
            MootdxIntradayQuery,
            MootdxLocalDataQuery,
            MootdxProvider,
            MootdxTransactionQuery,
        )

        bar_offset = int(provider_config.get("mootdx_bar_offset", 120))
        minute_bar_offset = int(provider_config.get("mootdx_minute_bar_offset", 240))
        bar_frequencies = tuple(provider_config.get("mootdx_frequencies", ("day",)))
        factory_options = dict(provider_config.get("mootdx_factory_options", {}))
        for symbol in symbols:
            for frequency in bar_frequencies:
                frequency_text = str(frequency)
                offset = minute_bar_offset if frequency_text in {"1m", "5m", "15m", "30m", "1h"} else bar_offset
                label = "mootdx_bars" if frequency_text in {"day", "daily", "d", "1d"} else f"mootdx_bars_{safe_task_label(frequency_text)}"
                tasks[f"equity.{symbol}.{label}"] = (
                    lambda s=symbol, freq=frequency_text, count=offset, options=factory_options: MootdxProvider(
                        **options
                    ).get_bars(MootdxBarQuery(symbol=s, frequency=freq, offset=count))
                )
            if bool(provider_config.get("mootdx_realtime", True)):
                tasks[f"equity.{symbol}.mootdx_realtime"] = (
                    lambda s=symbol, options=factory_options: MootdxProvider(**options).get_realtime_quotes(s)
                )
            if bool(provider_config.get("mootdx_intraday", False)):
                tasks[f"equity.{symbol}.mootdx_intraday"] = (
                    lambda s=symbol, options=factory_options: MootdxProvider(**options).get_intraday_points(
                        MootdxIntradayQuery(symbol=s)
                    )
                )
            if bool(provider_config.get("mootdx_order_book", False)):
                tasks[f"equity.{symbol}.mootdx_order_book"] = (
                    lambda s=symbol, options=factory_options: MootdxProvider(**options).get_order_books(s)
                )
            if bool(provider_config.get("mootdx_financials", True)):
                tasks[f"equity.{symbol}.mootdx_financial_summary"] = (
                    lambda s=symbol, options=factory_options: MootdxProvider(**options).get_financial_summary(s)
                )
            if bool(provider_config.get("mootdx_shareholders", False)):
                tasks[f"equity.{symbol}.mootdx_shareholders"] = (
                    lambda s=symbol, options=factory_options: MootdxProvider(**options).get_shareholder_snapshot(s)
                )
            if bool(provider_config.get("mootdx_company_profile", False)):
                sections = tuple(provider_config.get("mootdx_company_profile_sections", ()))
                include_all = bool(provider_config.get("mootdx_company_profile_include_all", not sections))
                tasks[f"equity.{symbol}.mootdx_company_profile"] = (
                    lambda s=symbol, profile_sections=sections, all_sections=include_all, options=factory_options: MootdxProvider(
                        **options
                    ).get_company_profile(
                        MootdxCompanyProfileQuery(
                            symbol=s,
                            sections=profile_sections,
                            include_all=all_sections,
                        )
                    )
                )
            if bool(provider_config.get("mootdx_transactions", False)):
                transaction_offset = int(provider_config.get("mootdx_transaction_offset", 80))
                tasks[f"equity.{symbol}.mootdx_transactions"] = (
                    lambda s=symbol, options=factory_options: MootdxProvider(**options).get_transactions(
                        MootdxTransactionQuery(symbol=s, offset=transaction_offset)
                    )
                )
            tdxdir = str(provider_config.get("mootdx_local_tdxdir", "") or "")
            if tdxdir:
                local_frequencies = tuple(provider_config.get("mootdx_local_frequencies", ("day",)))
                local_market = str(provider_config.get("mootdx_local_market", "std"))
                for frequency in local_frequencies:
                    tasks[f"equity.{symbol}.mootdx_local_{safe_task_label(frequency)}"] = (
                        lambda s=symbol, freq=str(frequency), market=local_market, root=tdxdir: MootdxProvider().read_local_bars(
                            MootdxLocalDataQuery(symbol=s, tdxdir=root, frequency=freq, market=market)
                        )
                    )

        index_symbols = tuple(provider_config.get("mootdx_index_symbols", ()))
        index_frequencies = tuple(provider_config.get("mootdx_index_frequencies", ("day",)))
        for index_symbol in index_symbols:
            for frequency in index_frequencies:
                tasks[f"equity.{index_symbol}.mootdx_index_{safe_task_label(frequency)}"] = (
                    lambda s=str(index_symbol), freq=str(frequency), options=factory_options: MootdxProvider(
                        **options
                    ).get_bars(MootdxBarQuery(symbol=s, frequency=freq, offset=bar_offset, is_index=True))
                )
    return tasks


def safe_task_label(value: object) -> str:
    return str(value).replace(" ", "_").replace("/", "_").replace(".", "_")[:80]
