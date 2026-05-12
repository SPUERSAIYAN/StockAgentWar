from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal


OrderAction = Literal["BUY", "SELL"]


class SimulatedOrderService:
    def __init__(
        self,
        *,
        order_log_file: str | Path,
        commission_rate: float = 0.0003,
        stamp_tax_rate: float = 0.0005,
        mode: str = "SIMULATED",
    ):
        self.order_log_file = Path(order_log_file)
        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.mode = mode.upper()

    def execute_order(
        self,
        *,
        stock: dict[str, Any],
        action: OrderAction,
        price: float,
        quantity: int,
        trigger_reason: str,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        if self.mode != "SIMULATED":
            raise RuntimeError("Only SIMULATED order execution is implemented. PAPER/LIVE are reserved.")

        normalized_quantity = normalize_a_share_quantity(quantity)
        if normalized_quantity <= 0:
            raise ValueError("A-share order quantity must be at least one 100-share lot.")

        timestamp = timestamp or datetime.now()
        amount = round(price * normalized_quantity, 2)
        commission = round(amount * self.commission_rate, 2)
        stamp_tax = round(amount * self.stamp_tax_rate, 2) if action == "SELL" else 0.0
        order = {
            "symbol": stock.get("symbol", ""),
            "name": stock.get("name", ""),
            "action": action,
            "price": round(price, 2),
            "quantity": normalized_quantity,
            "amount": amount,
            "commission": commission,
            "stamp_tax": stamp_tax,
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "trigger_reason": trigger_reason,
            "mode": self.mode,
        }
        self.append_order(order)
        return order

    def append_order(self, order: dict[str, Any]) -> None:
        data = self.load_order_log()
        data.setdefault("orders", []).append(order)
        self.order_log_file.parent.mkdir(parents=True, exist_ok=True)
        self.order_log_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_order_log(self) -> dict[str, Any]:
        if not self.order_log_file.exists():
            return {"orders": []}
        try:
            data = json.loads(self.order_log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"orders": []}
        if not isinstance(data, dict):
            return {"orders": []}
        if not isinstance(data.get("orders"), list):
            data["orders"] = []
        return data

    def position_quantity(self, symbol: str) -> int:
        quantity = 0
        for order in self.load_order_log().get("orders", []):
            if order.get("symbol") != symbol:
                continue
            if order.get("action") == "BUY":
                quantity += int(order.get("quantity") or 0)
            elif order.get("action") == "SELL":
                quantity -= int(order.get("quantity") or 0)
        return max(quantity, 0)

    def can_sell(self, symbol: str, today: date) -> bool:
        if self.position_quantity(symbol) <= 0:
            return False
        for order in self.load_order_log().get("orders", []):
            if order.get("symbol") != symbol or order.get("action") != "BUY":
                continue
            order_date = parse_order_date(str(order.get("timestamp", "")))
            if order_date == today:
                return False
        return True


def normalize_a_share_quantity(quantity: Any) -> int:
    try:
        value = int(quantity)
    except (TypeError, ValueError):
        return 0
    return max(value // 100 * 100, 0)


def parse_order_date(timestamp: str) -> date | None:
    try:
        return datetime.strptime(timestamp[:19], "%Y-%m-%d %H:%M:%S").date()
    except ValueError:
        return None
