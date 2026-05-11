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
        from digital_oracle import TencentFinanceProvider, TencentStockMetricsQuery

        for symbol in symbols:
            tasks[f"equity.{symbol}.tencent_metrics"] = (
                lambda s=symbol: TencentFinanceProvider().get_stock_metrics(
                    TencentStockMetricsQuery(symbols=(s,))
                )
            )

    if include_mootdx:
        from digital_oracle import (
            MootdxBarQuery,
            MootdxProvider,
            MootdxTransactionQuery,
        )

        bar_offset = int(provider_config.get("mootdx_bar_offset", 120))
        factory_options = dict(provider_config.get("mootdx_factory_options", {}))
        for symbol in symbols:
            tasks[f"equity.{symbol}.mootdx_bars"] = (
                lambda s=symbol, options=factory_options: MootdxProvider(**options).get_bars(
                    MootdxBarQuery(symbol=s, frequency="day", offset=bar_offset)
                )
            )
            if bool(provider_config.get("mootdx_realtime", True)):
                tasks[f"equity.{symbol}.mootdx_realtime"] = (
                    lambda s=symbol, options=factory_options: MootdxProvider(**options).get_realtime_quotes(s)
                )
            if bool(provider_config.get("mootdx_financials", True)):
                tasks[f"equity.{symbol}.mootdx_financial_summary"] = (
                    lambda s=symbol, options=factory_options: MootdxProvider(**options).get_financial_summary(s)
                )
            if bool(provider_config.get("mootdx_transactions", False)):
                transaction_offset = int(provider_config.get("mootdx_transaction_offset", 80))
                tasks[f"equity.{symbol}.mootdx_transactions"] = (
                    lambda s=symbol, options=factory_options: MootdxProvider(**options).get_transactions(
                        MootdxTransactionQuery(symbol=s, offset=transaction_offset)
                    )
                )
    return tasks

