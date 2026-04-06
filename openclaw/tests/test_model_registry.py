"""Tests for openclaw.model_registry — drift detection."""
import unittest

from openclaw.model_registry import ModelRegistry


class TestModelRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = ModelRegistry()

    def test_diff_detects_missing_models(self):
        available = [
            {"id": "openai/gpt-4o-mini", "provider": "openai"},
            {"id": "openai/gpt-4o", "provider": "openai"},
        ]
        result = self.registry.diff_configured_vs_available(available)
        # "openai/gpt-5.2-codex" is configured but not in available
        self.assertIn("openai/gpt-5.2-codex", result["missing_from_provider"])

    def test_diff_returns_correct_structure(self):
        available = [{"id": "model-a", "provider": "openai"}]
        result = self.registry.diff_configured_vs_available(available)
        self.assertIn("configured", result)
        self.assertIn("available_count", result)
        self.assertIn("missing_from_provider", result)
        self.assertIn("newer_available", result)
        self.assertIn("checked_at", result)

    def test_diff_empty_available(self):
        result = self.registry.diff_configured_vs_available([])
        self.assertEqual(result["available_count"], 0)
        self.assertEqual(result["missing_from_provider"], [])


if __name__ == "__main__":
    unittest.main()
