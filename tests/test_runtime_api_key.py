from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import patch

from agents.information_agent import create_openrouter_model
from main import ensure_runtime_openrouter_api_key, has_openrouter_model


class RuntimeApiKeyTests(unittest.TestCase):
    def test_openrouter_model_requires_runtime_api_key(self) -> None:
        fake_module = types.ModuleType("langchain_openai")
        fake_module.ChatOpenAI = object
        with (
            patch.dict(sys.modules, {"langchain_openai": fake_module}),
            patch.dict(os.environ, {"OPENROUTER_API_KEY": "env-only"}),
        ):
            with self.assertRaisesRegex(RuntimeError, "Provide it at runtime"):
                create_openrouter_model({"provider": "openrouter", "model": "test-model"})

    def test_ensure_runtime_openrouter_api_key_injects_cli_argument(self) -> None:
        configs = {
            "information": {
                "model": {"provider": "openrouter", "model": "test-model"},
            }
        }

        ensure_runtime_openrouter_api_key(configs, "sk-test")

        self.assertEqual(configs["information"]["model"]["api_key"], "sk-test")

    def test_ensure_runtime_openrouter_api_key_prompts_when_argument_missing(self) -> None:
        configs = {
            "information": {
                "model": {"provider": "openrouter", "model": "test-model"},
            }
        }

        with patch("getpass.getpass", return_value="sk-prompted") as getpass_mock:
            ensure_runtime_openrouter_api_key(configs, "")

        getpass_mock.assert_called_once()
        self.assertEqual(configs["information"]["model"]["api_key"], "sk-prompted")

    def test_mock_configs_do_not_require_api_key(self) -> None:
        configs = {
            "information": {
                "model": {"provider": "mock", "model": "mock-information"},
            }
        }

        ensure_runtime_openrouter_api_key(configs, "")

        self.assertFalse(has_openrouter_model(configs))


if __name__ == "__main__":
    unittest.main()
