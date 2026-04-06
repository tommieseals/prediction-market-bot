"""Tests for openclaw.run_lock — file-based concurrency guard."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openclaw.run_lock import RunLock, LockError


class TestRunLock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.lock_path = Path(self.tmp) / ".run_lock"

    def test_acquire_and_release(self):
        lock = RunLock("test", lock_path=self.lock_path)
        lock.acquire()
        self.assertTrue(self.lock_path.exists())
        lock.release()
        self.assertFalse(self.lock_path.exists())

    def test_context_manager(self):
        with RunLock("ctx", lock_path=self.lock_path):
            self.assertTrue(self.lock_path.exists())
        self.assertFalse(self.lock_path.exists())

    def test_double_acquire_raises(self):
        lock1 = RunLock("first", lock_path=self.lock_path)
        lock1.acquire()
        lock2 = RunLock("second", lock_path=self.lock_path)
        with self.assertRaises(LockError):
            lock2.acquire()
        lock1.release()

    def test_stale_detection(self):
        lock = RunLock("stale", lock_path=self.lock_path, max_age_seconds=1)
        lock.acquire()
        # Mock time.time to simulate staleness
        import time
        real_time = time.time
        with patch("time.time", return_value=real_time() + 100):
            self.assertTrue(lock.is_stale())
            self.assertFalse(lock.is_locked())

    def test_is_locked(self):
        lock = RunLock("test", lock_path=self.lock_path)
        self.assertFalse(lock.is_locked())
        lock.acquire()
        self.assertTrue(lock.is_locked())
        lock.release()


if __name__ == "__main__":
    unittest.main()
