from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from agents.information_agent import MockChatModel, invoke_text
from agents.trace_logger import log_agent_output


class TraceLoggingTests(unittest.TestCase):
    def test_model_call_logs_success_and_output_status(self) -> None:
        buffer = io.StringIO()

        with patch.dict("os.environ", {"AGENT_TRACE": "1"}, clear=False), redirect_stderr(buffer):
            text = invoke_text(
                MockChatModel("mock-information"),
                [{"role": "user", "content": "Analyze AAPL"}],
                agent_name="information",
                model_config={"provider": "mock", "model": "mock-information"},
            )
            log_agent_output("information", "info_report", text)

        logs = buffer.getvalue()
        self.assertIn("MODEL CALL START agent=information provider=mock model=mock-information", logs)
        self.assertIn("MODEL CALL OK agent=information", logs)
        self.assertIn("AGENT OUTPUT agent=information key=info_report output_status=ok", logs)

    def test_model_call_logs_empty_output(self) -> None:
        buffer = io.StringIO()

        with patch.dict("os.environ", {"AGENT_TRACE": "1"}, clear=False), redirect_stderr(buffer):
            invoke_text(
                EmptyModel(),
                [{"role": "user", "content": "empty"}],
                agent_name="empty_agent",
                model_config={"provider": "custom", "model": "empty"},
            )

        logs = buffer.getvalue()
        self.assertIn("MODEL CALL OK agent=empty_agent", logs)
        self.assertIn("output_status=empty", logs)


class EmptyModel:
    def invoke(self, messages: list[dict[str, str]]) -> str:
        return ""
