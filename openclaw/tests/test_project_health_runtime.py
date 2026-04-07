"""Tests for runtime project health behavior that the main loop depends on."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openclaw.project_health import ProjectHealth


class TestProjectHealthRuntime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.adapters_path = Path(self.tmp) / "project_adapters.json"
        self.status_path = Path(self.tmp) / "project_status.json"
        adapters = {
            "legion": {"description": "Legion 🎯"},
            "taskbot": {"description": "TaskBot"},
        }
        self.adapters_path.write_text(json.dumps(adapters, ensure_ascii=False), encoding="utf-8")
        self.health = ProjectHealth(status_path=self.status_path, adapters_path=self.adapters_path)

    def test_check_all_loads_utf8_adapters_without_crashing(self):
        with patch.object(
            self.health,
            "_check_project",
            side_effect=[
                {"status": "unknown", "days_idle": 0, "timestamp": "2026-04-06T00:00:00+00:00"},
                {"status": "active", "days_idle": 0, "timestamp": "2026-04-06T00:00:00+00:00"},
            ],
        ):
            results = self.health.check_all()
        self.assertIn("legion", results["stalled"])
        self.assertIn("taskbot", results["healthy"])
        written = json.loads(self.status_path.read_text(encoding="utf-8"))
        self.assertEqual(len(written["projects"]), 2)

    def test_safe_int_prevents_timeout_strings_from_crashing(self):
        with patch.object(
            self.health,
            "_run_ssh_command",
            side_effect=["yes", "timeout", "timeout"],
        ):
            result = self.health._ssh_check(
                host="100.88.105.106",
                user="tommie",
                checks={
                    "main_repo": "test",
                    "chrome_running": "test",
                    "python_processes": "test",
                },
                project_id="legion",
            )
        self.assertEqual(result["status"], "idle")

    def test_generic_rtx_repo_check_uses_powershell(self):
        adapter = {
            "machine": "rtx",
            "repo_path": r"C:\Users\User\clawd\taskbot",
        }

        def fake_run(cmd, capture_output, text, timeout, encoding, errors, shell):
            self.assertTrue(shell)
            self.assertIn("powershell -NoProfile -Command", cmd)
            return SimpleNamespace(stdout="yes\n", stderr="", returncode=0)

        with patch("platform.system", return_value="Windows"), patch("subprocess.run", side_effect=fake_run):
            result = self.health._check_generic("taskbot", adapter)

        self.assertEqual(result["repo_exists"], "yes")

    def test_terminator_check_runs_locally_on_windows(self):
        outputs = iter(["yes", "2026-04-06 06:10:53 -0500 Commit", "2", "yes"])

        with patch("platform.system", return_value="Windows"), patch.object(
            self.health,
            "_run_local_command",
            side_effect=lambda command: next(outputs),
        ):
            result = self.health.check_terminatorbot()

        self.assertEqual(result["machine"], "rtx")
        self.assertEqual(result["repo_exists"], "yes")
        self.assertEqual(result["status"], "active")


if __name__ == "__main__":
    unittest.main()
