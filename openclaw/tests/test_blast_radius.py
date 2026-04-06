"""Tests for blast radius — worker limit enforcement."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openclaw.worker_manager import WorkerManager, WorkerLimitError


class TestBlastRadius(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.registry_path = Path(self.tmp) / "worker_registry.json"
        self.mgr = WorkerManager(registry_path=self.registry_path)

    def test_local_worker_limit_raises(self):
        with patch("openclaw.config.Config.MAX_CONCURRENT_LOCAL_WORKERS", 3):
            self.mgr.spawn_local_worker("m1", "tester")
            self.mgr.spawn_local_worker("m2", "monitor")
            self.mgr.spawn_local_worker("m3", "patcher")
            with self.assertRaises(WorkerLimitError):
                self.mgr.spawn_local_worker("m4", "researcher")

    def test_under_limit_succeeds(self):
        with patch("openclaw.config.Config.MAX_CONCURRENT_LOCAL_WORKERS", 10):
            worker = self.mgr.spawn_local_worker("m1", "tester")
        self.assertIn("worker_id", worker)

    def test_recalled_workers_free_capacity(self):
        with patch("openclaw.config.Config.MAX_CONCURRENT_LOCAL_WORKERS", 2):
            w1 = self.mgr.spawn_local_worker("m1", "tester")
            self.mgr.spawn_local_worker("m2", "monitor")
            # Recall one to free capacity
            self.mgr.recall_worker(w1["worker_id"])
            # Should now succeed
            w3 = self.mgr.spawn_local_worker("m3", "patcher")
            self.assertIn("worker_id", w3)


if __name__ == "__main__":
    unittest.main()
