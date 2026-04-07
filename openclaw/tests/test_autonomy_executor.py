"""Tests for low-risk autonomous execution."""
import unittest

from openclaw.autonomy_executor import execute_safe_first_step


class FakeRemoteExec:
    def __init__(self):
        self.calls = []

    def run_remote_tests(self, project_id):
        self.calls.append(("tests", project_id))
        return {"exit_code": 0, "stdout": "tests ok", "stderr": ""}

    def run_remote_step(self, project_id, command, dry_run=False, timeout=None):
        self.calls.append(("step", project_id, command, dry_run, timeout))
        return {"exit_code": 0, "stdout": "repo_ok", "stderr": ""}


class FakeWorkerManager:
    def __init__(self):
        self.events = []

    def mark_running(self, worker_id):
        self.events.append(("running", worker_id))

    def append_action_log(self, worker_id, entry):
        self.events.append(("log", worker_id, entry["status"]))

    def mark_done(self, worker_id, note):
        self.events.append(("done", worker_id, note))

    def mark_failed(self, worker_id, note):
        self.events.append(("failed", worker_id, note))


class TestAutonomyExecutor(unittest.TestCase):
    def test_execute_safe_first_step_prefers_status_command(self):
        rx = FakeRemoteExec()
        action = {"project_id": "legion", "action_type": "unblock", "can_run_tests": True}
        adapter = {
            "status_command": "python3 ~/clawd/scripts/job-auth-status.py",
            "test_command": "pytest -q",
            "allowed_actions": ["run_tests", "read_status"],
        }

        result = execute_safe_first_step(action, adapter, rx)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "status_command")
        self.assertEqual(rx.calls[0], ("step", "legion", "python3 ~/clawd/scripts/job-auth-status.py", False, 45))

    def test_execute_safe_first_step_runs_tests_when_available(self):
        rx = FakeRemoteExec()
        wm = FakeWorkerManager()
        action = {"project_id": "legion", "action_type": "unblock", "can_run_tests": True}
        adapter = {"test_command": "pytest -q", "allowed_actions": ["run_tests", "read_status"]}

        result = execute_safe_first_step(action, adapter, rx, wm, "wkr_1")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "tests")
        self.assertEqual(rx.calls[0], ("tests", "legion"))

    def test_execute_safe_first_step_falls_back_to_status_probe(self):
        rx = FakeRemoteExec()
        action = {
            "project_id": "taskbot",
            "action_type": "investigate",
            "can_run_tests": False,
        }
        adapter = {
            "machine": "rtx",
            "repo_path": r"C:\Users\User\clawd\taskbot",
            "allowed_actions": ["read_status"],
        }

        result = execute_safe_first_step(action, adapter, rx)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "status_probe")
        self.assertEqual(rx.calls[0][0], "step")


if __name__ == "__main__":
    unittest.main()
