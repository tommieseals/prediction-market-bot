"""Tests for openclaw.eval_harness — independent evaluation."""
import unittest

from openclaw.eval_harness import EvalHarness


class TestEvalHarness(unittest.TestCase):
    def setUp(self):
        self.harness = EvalHarness()

    def test_run_eval_returns_dict_with_aggregate(self):
        result = self.harness.run_eval("test_variant")
        self.assertIsInstance(result, dict)
        self.assertIn("aggregate_score", result)
        self.assertIsInstance(result["aggregate_score"], float)

    def test_fixed_tasks_has_10_items(self):
        result = self.harness.run_eval("test_variant")
        self.assertEqual(len(result["fixed_tasks"]), 10)

    def test_hidden_tests_has_5_items(self):
        result = self.harness.run_eval("test_variant")
        self.assertEqual(len(result["hidden_tests"]), 5)

    def test_each_task_has_required_fields(self):
        result = self.harness.run_eval("test_variant")
        for task in result["fixed_tasks"]:
            self.assertIn("id", task)
            self.assertIn("category", task)
            self.assertIn("score", task)


if __name__ == "__main__":
    unittest.main()
