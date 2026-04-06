"""Tests for openclaw.opportunity_watcher — robots.txt compliance."""
import unittest
from unittest.mock import patch, MagicMock

from openclaw.opportunity_watcher import OpportunityWatcher


class TestRobotsCompliance(unittest.TestCase):
    def test_robots_allowed_returns_bool_when_no_requests(self):
        """Without the requests library, robots_allowed returns False."""
        with patch("openclaw.opportunity_watcher.requests", None):
            watcher = OpportunityWatcher()
            result = watcher.robots_allowed("https://example.com/page")
        self.assertIsInstance(result, bool)
        self.assertFalse(result)

    def test_robots_allowed_returns_true_on_200(self):
        """robots_allowed returns True when robots.txt allows our path."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "User-agent: *\nAllow: /\n"
        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_resp
        with patch("openclaw.opportunity_watcher.requests", mock_requests):
            watcher = OpportunityWatcher()
            result = watcher.robots_allowed("https://example.com/blog")
        self.assertTrue(result)

    def test_robots_allowed_returns_false_on_disallow(self):
        """robots_allowed returns False when path is disallowed."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "User-agent: *\nDisallow: /private\n"
        mock_requests = MagicMock()
        mock_requests.get.return_value = mock_resp
        with patch("openclaw.opportunity_watcher.requests", mock_requests):
            watcher = OpportunityWatcher()
            result = watcher.robots_allowed("https://example.com/private/data")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
