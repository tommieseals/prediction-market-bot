"""OpenClaw Anomaly — SRE Recurrence & Closure Engine.

Detect recurring alerts (3+ in 7 days = auto-open RCA mission).
Enforce closure only after verification + stability window.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

from openclaw.config import Config
from openclaw.schemas import IncidentRecord


class RecurrenceEngine:
    """Convert repeated alerts into root-cause missions."""

    def __init__(self, incidents_path: Path | None = None):
        self.path = incidents_path or Config.INCIDENTS_PATH

    def _load_incidents(self) -> list[dict]:
        if not self.path.exists():
            return []
        incidents = []
        try:
            with open(self.path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            incidents.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            pass
        return incidents

    def _append_incident(self, incident: dict) -> None:
        IncidentRecord.validate(incident)
        with open(self.path, "a") as f:
            f.write(json.dumps(incident) + "\n")

    def detect_recurring_incidents(self, alerts: list[dict]) -> list[dict]:
        """Detect alert signatures that recur >= threshold in window.

        Args:
            alerts: List of {alert_signature, timestamp} dicts.

        Returns:
            List of alert_signatures that need RCA missions.
        """
        window = timedelta(days=Config.RECURRENCE_WINDOW_DAYS)
        now = datetime.now(timezone.utc)
        cutoff = now - window

        recent_sigs = []
        for alert in alerts:
            try:
                ts = datetime.fromisoformat(alert["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    recent_sigs.append(alert["alert_signature"])
            except (ValueError, KeyError):
                continue

        counts = Counter(recent_sigs)
        recurring = [
            {"alert_signature": sig, "occurrences": count}
            for sig, count in counts.items()
            if count >= Config.RECURRENCE_THRESHOLD
        ]
        return recurring

    def open_rca_mission(self, alert_signature: str, occurrences: int) -> dict:
        """Create an incident record for a recurring alert."""
        incident = {
            "incident_id": f"inc_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "alert_signature": alert_signature,
            "state": "opened",
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "occurrences": occurrences,
            "suspected_root_cause": None,
            "attempted_fix": None,
            "fix_applied_at": None,
            "verification_result": None,
            "stable_since": None,
            "closed_at": None,
            "reopened_at": None,
            "preventive_action": None,
        }
        self._append_incident(incident)
        return incident

    def update_incident(self, incident_id: str, updates: dict) -> dict | None:
        """Update an existing incident (rewrite entire file)."""
        incidents = self._load_incidents()
        target = None
        for inc in incidents:
            if inc.get("incident_id") == incident_id:
                inc.update(updates)
                target = inc
                break
        if target is None:
            return None
        # Rewrite
        with open(self.path, "w") as f:
            for inc in incidents:
                f.write(json.dumps(inc) + "\n")
        return target

    def close_incident_after_verify(
        self,
        incident_id: str,
        verification_result: str,
        preventive_action: str | None = None,
    ) -> tuple[bool, str]:
        """Attempt to close an incident. Requires stability window.

        Returns:
            (closed, reason)
        """
        incidents = self._load_incidents()
        target = None
        for inc in incidents:
            if inc.get("incident_id") == incident_id:
                target = inc
                break
        if target is None:
            return False, f"Incident {incident_id} not found."

        if target["state"] == "closed":
            return False, "Already closed."

        # Check stability window
        stable_since = target.get("stable_since")
        if stable_since:
            try:
                stable_dt = datetime.fromisoformat(stable_since)
                if stable_dt.tzinfo is None:
                    stable_dt = stable_dt.replace(tzinfo=timezone.utc)
                hours_stable = (datetime.now(timezone.utc) - stable_dt).total_seconds() / 3600
                if hours_stable < Config.INCIDENT_STABILITY_HOURS:
                    return False, (
                        f"Stability window not met: {hours_stable:.1f}h < "
                        f"{Config.INCIDENT_STABILITY_HOURS}h required."
                    )
            except ValueError:
                return False, "Cannot parse stable_since timestamp."
        else:
            return False, "No stable_since timestamp set. Mark stable first."

        self.update_incident(incident_id, {
            "state": "closed",
            "verification_result": verification_result,
            "preventive_action": preventive_action,
            "closed_at": datetime.now(timezone.utc).isoformat(),
        })
        return True, "Incident closed."

    def get_open_incidents(self) -> list[dict]:
        """Return all non-closed incidents."""
        return [
            inc for inc in self._load_incidents()
            if inc.get("state") not in ("closed",)
        ]
