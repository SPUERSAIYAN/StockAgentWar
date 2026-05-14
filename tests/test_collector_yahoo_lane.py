from __future__ import annotations

import unittest

from collectors.digital_oracle_collector import (
    gather_yahoo_tasks,
    is_yahoo_backed_task,
    split_yahoo_tasks,
)


class CollectorYahooLaneTests(unittest.TestCase):
    def test_yahoo_backed_tasks_are_classified_for_serial_lane(self) -> None:
        yahoo_labels = {
            "macro.price.SPY",
            "macro.price.USDCNY=X",
            "equity.AAPL.price_daily",
            "equity.AAPL.price_weekly",
            "equity.AAPL.options_nearest",
            "equity.AAPL.stooq_price_daily",
        }
        standard_labels = {
            "macro.treasury.exchange_rates",
            "macro.cme_fedwatch",
            "crypto.coingecko.global",
            "china.600000.SH.tencent_metrics",
            "equity.AAPL.edgar_form4",
        }

        for label in yahoo_labels:
            self.assertTrue(is_yahoo_backed_task(label), label)
        for label in standard_labels:
            self.assertFalse(is_yahoo_backed_task(label), label)

    def test_split_yahoo_tasks_preserves_labels(self) -> None:
        tasks = {
            "macro.cme_fedwatch": lambda: "cme",
            "macro.price.SPY": lambda: "spy",
            "macro.price.QQQ": lambda: "qqq",
            "macro.treasury.exchange_rates": lambda: "treasury",
        }

        standard_tasks, yahoo_tasks = split_yahoo_tasks(tasks)

        self.assertEqual(
            list(standard_tasks),
            ["macro.cme_fedwatch", "macro.treasury.exchange_rates"],
        )
        self.assertEqual(list(yahoo_tasks), ["macro.price.SPY", "macro.price.QQQ"])

    def test_serial_yahoo_gather_submits_one_task_at_a_time(self) -> None:
        submitted_batches: list[list[str]] = []

        def fake_gather(tasks, *, max_workers, timeout_seconds, fail_fast):
            submitted_batches.append(list(tasks))
            return FakeGatherResult(
                results={label: fn() for label, fn in tasks.items()},
                errors={},
            )

        results, errors = gather_yahoo_tasks(
            {
                "macro.price.SPY": lambda: "spy",
                "macro.price.QQQ": lambda: "qqq",
            },
            gather=fake_gather,
            max_workers=1,
            timeout_seconds=90,
        )

        self.assertEqual(submitted_batches, [["macro.price.SPY"], ["macro.price.QQQ"]])
        self.assertEqual(results, {"macro.price.SPY": "spy", "macro.price.QQQ": "qqq"})
        self.assertEqual(errors, {})


class FakeGatherResult:
    def __init__(self, *, results, errors) -> None:
        self.results = results
        self.errors = errors


if __name__ == "__main__":
    unittest.main()
