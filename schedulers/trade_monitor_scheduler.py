from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, time as day_time
from pathlib import Path
from typing import Any, Callable

import yaml

from services.order_service import SimulatedOrderService, normalize_a_share_quantity


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TradeMonitorScheduler:
    def __init__(
        self,
        *,
        plan_file: str | Path,
        order_log_file: str | Path,
        interval_seconds: int = 60,
        mode: str = "SIMULATED",
        commission_rate: float = 0.0003,
        stamp_tax_rate: float = 0.0005,
        price_lookup: Callable[[str], float | None] | None = None,
    ):
        self.plan_file = Path(plan_file)
        self.interval_seconds = interval_seconds
        self.mode = mode.upper()
        self.price_lookup = price_lookup or fetch_realtime_price
        self.order_service = SimulatedOrderService(
            order_log_file=order_log_file,
            commission_rate=commission_rate,
            stamp_tax_rate=stamp_tax_rate,
            mode=self.mode,
        )
        self.executed_order_keys = self.load_executed_order_keys()

    def run(self) -> None:
        while True:
            self.run_once()
            time.sleep(self.interval_seconds)

    def run_once(
        self,
        *,
        now: datetime | None = None,
        ignore_trading_time: bool = False,
    ) -> list[dict[str, Any]]:
        now = now or datetime.now()
        if not ignore_trading_time and not is_a_share_trading_time(now):
            return []

        plan = self.load_plan()
        orders: list[dict[str, Any]] = []
        for stock in plan.get("monitored_stocks", []):
            if not self.is_valid_plan_stock(stock, now.date()):
                continue
            symbol = str(stock.get("symbol", ""))
            current_price = self.price_lookup(symbol)
            if current_price is None:
                continue
            order = self.evaluate_stock(stock, float(current_price), now)
            if order:
                orders.append(order)
        return orders

    def evaluate_stock(
        self,
        stock: dict[str, Any],
        current_price: float,
        now: datetime,
    ) -> dict[str, Any] | None:
        symbol = str(stock.get("symbol", ""))
        position = self.order_service.position_quantity(symbol)
        can_sell = self.order_service.can_sell(symbol, now.date())

        stop_loss_price = to_float(stock.get("stop_loss_price"))
        if position > 0 and can_sell and stop_loss_price is not None and current_price <= stop_loss_price:
            return self.execute_once(stock, "SELL", current_price, position, "股价触及止损价", now)

        take_profit_price = to_float(stock.get("take_profit_price"))
        if position > 0 and can_sell and take_profit_price is not None and current_price >= take_profit_price:
            return self.execute_once(stock, "SELL", current_price, position, "股价触及止盈价", now)

        buy_trigger_price = to_float(stock.get("buy_trigger_price"))
        if position <= 0 and buy_trigger_price is not None and current_price <= buy_trigger_price:
            quantity = normalize_a_share_quantity(stock.get("quantity"))
            return self.execute_once(stock, "BUY", current_price, quantity, "股价低于买入触发价", now)

        sell_trigger_price = to_float(stock.get("sell_trigger_price"))
        if position > 0 and can_sell and sell_trigger_price is not None and current_price >= sell_trigger_price:
            return self.execute_once(stock, "SELL", current_price, position, "股价达到卖出触发价", now)

        return None

    def execute_once(
        self,
        stock: dict[str, Any],
        action: str,
        price: float,
        quantity: int,
        reason: str,
        timestamp: datetime,
    ) -> dict[str, Any] | None:
        key = build_order_key(stock, action, reason)
        if key in self.executed_order_keys:
            return None
        order = self.order_service.execute_order(
            stock=stock,
            action=action,  # type: ignore[arg-type]
            price=price,
            quantity=quantity,
            trigger_reason=f"{reason} {price:.2f}",
            timestamp=timestamp,
        )
        self.executed_order_keys.add(key)
        return order

    def load_plan(self) -> dict[str, Any]:
        if not self.plan_file.exists():
            return {"monitored_stocks": []}
        try:
            data = json.loads(self.plan_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"monitored_stocks": []}
        return data if isinstance(data, dict) else {"monitored_stocks": []}

    def is_valid_plan_stock(self, stock: dict[str, Any], today: date) -> bool:
        valid_from = parse_date(str(stock.get("valid_from") or ""))
        valid_until = parse_date(str(stock.get("valid_until") or ""))
        if valid_from and today < valid_from:
            return False
        if valid_until and today > valid_until:
            return False
        return bool(stock.get("symbol"))

    def load_executed_order_keys(self) -> set[str]:
        keys: set[str] = set()
        for order in self.order_service.load_order_log().get("orders", []):
            keys.add(
                build_order_key(
                    order,
                    str(order.get("action", "")),
                    str(order.get("trigger_reason", "")).split()[0],
                )
            )
        return keys


def fetch_realtime_price(symbol: str) -> float | None:
    try:
        from collectors.digital_oracle import TencentFinanceProvider, TencentStockMetricsQuery
    except Exception:
        return None
    metrics = TencentFinanceProvider().get_stock_metrics(TencentStockMetricsQuery(symbols=(symbol,)))
    if not metrics:
        return None
    return to_float(getattr(metrics[0], "price", None))


def is_a_share_trading_time(moment: datetime) -> bool:
    current = moment.time()
    return (
        day_time(9, 30) <= current <= day_time(11, 30)
        or day_time(13, 0) <= current <= day_time(15, 0)
    )


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_order_key(stock: dict[str, Any], action: str, reason: str) -> str:
    return ":".join(
        [
            str(stock.get("symbol", "")),
            action.upper(),
            reason,
        ]
    )


def load_scheduler_from_config(
    *,
    config_path: Path,
    plan_file: str | None,
    interval: int | None,
    mode: str | None,
) -> TradeMonitorScheduler:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    monitor_config = dict((config or {}).get("trade_monitor", {}) or {})
    trader_config = dict((config or {}).get("agents", {}).get("trader", {}) or {})
    simulated_config = dict(trader_config.get("simulated", {}) or {})

    resolved_plan_file = PROJECT_ROOT / (plan_file or monitor_config.get("plan_file", "data/trade_plan.json"))
    order_log_file = PROJECT_ROOT / monitor_config.get("order_log_file", "data/order_log.json")
    return TradeMonitorScheduler(
        plan_file=resolved_plan_file,
        order_log_file=order_log_file,
        interval_seconds=int(interval or monitor_config.get("interval_seconds", 60)),
        mode=mode or monitor_config.get("mode", "SIMULATED"),
        commission_rate=float(simulated_config.get("commission_rate", 0.0003)),
        stamp_tax_rate=float(simulated_config.get("stamp_tax_rate", 0.0005)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run A-share trade monitor scheduler.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.yaml")
    parser.add_argument("--plan-file", default=None)
    parser.add_argument("--interval", type=int, default=None)
    parser.add_argument("--mode", default=None, choices=("SIMULATED", "PAPER", "LIVE"))
    parser.add_argument("--run-once", action="store_true")
    parser.add_argument("--ignore-trading-time", action="store_true")
    args = parser.parse_args()

    scheduler = load_scheduler_from_config(
        config_path=args.config,
        plan_file=args.plan_file,
        interval=args.interval,
        mode=args.mode,
    )
    if args.run_once:
        orders = scheduler.run_once(ignore_trading_time=args.ignore_trading_time)
        print(json.dumps({"orders": orders}, ensure_ascii=False, indent=2))
        return
    scheduler.run()


if __name__ == "__main__":
    main()
