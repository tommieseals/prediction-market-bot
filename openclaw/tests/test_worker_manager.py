"""Tests for openclaw.worker_manager — spawn, recall, expire, limits."""
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from openclaw.worker_manager import WorkerManager, WorkerLimitError, WorkerState


class TestWorkerManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.registry_path = Path(self.tmp) / "worker_registry.json"
        self.mgr = WorkerManager(registry_path=self.registry_path)

    def test_spawn_local_creates_record(self):
        worker = self.mgr.spawn_local_worker("mission_1", "tester")
        self.assertIn("worker_id", worker)
        self.assertEqual(worker["state"], WorkerState.PENDING)
        self.assertEqual(worker["worker_type"], "tester")

    def test_recall_worker_changes_state(self):
        worker = self.mgr.spawn_local_worker("m1", "monitor")
        result = self.mgr.recall_worker(worker["worker_id"], "test recall")
        self.assertIsNotNone(result)
        self.assertEqual(result["state"], WorkerState.RECALLED)

    def test_expire_stale_workers(self):
        # Create a worker with past spawn time
        worker = self.mgr.spawn_local_worker("m2", "patcher", ttl_minutes=1)
        # Manually backdate spawned_at
        registry = json.loads(self.registry_path.read_text())
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        registry["workers"][0]["spawned_at"] = old_time
        self.registry_path.write_text(json.dumps(registry))
        expired = self.mgr.expire_stale_workers()
        self.assertEqual(expired, 1)

    def test_worker_limit_error_at_cap(self):
        from unittest.mock import patch
        with patch("openclaw.config.Config.MAX_CONCURRENT_LOCAL_WORKERS", 2):
            self.mgr.spawn_local_worker("m1", "tester")
            self.mgr.spawn_local_worker("m2", "monitor")
            with self.assertRaises(WorkerLimitError):
                self.mgr.spawn_local_worker("m3", "patcher")


if __name__ == "__main__":
    unittest.main()
