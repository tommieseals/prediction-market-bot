"""OpenClaw Anomaly — Matrix Inventory (CMDB).

Canonical store for machines, projects, services, resources, accounts, models.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config


class MatrixInventory:
    """CMDB-style inventory for the workspace."""

    def __init__(self, path: Path | None = None):
        self.path = path or Config.MATRIX_INVENTORY_PATH

    def load_inventory(self) -> dict:
        if not self.path.exists():
            return self._default()
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return self._default()

    def save_inventory_atomic(self, data: dict) -> None:
        data["last_updated"] = datetime.now(timezone.utc).isoformat()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(self.path))

    def update_machine_snapshot(self, machine_id: str, snapshot: dict) -> None:
        inv = self.load_inventory()
        for m in inv.get("machines", []):
            if m["id"] == machine_id:
                m.update(snapshot)
                m["last_seen"] = datetime.now(timezone.utc).isoformat()
                self.save_inventory_atomic(inv)
                return
        # New machine
        snapshot["id"] = machine_id
        snapshot["last_seen"] = datetime.now(timezone.utc).isoformat()
        inv.setdefault("machines", []).append(snapshot)
        self.save_inventory_atomic(inv)

    def update_project_snapshot(self, project_id: str, snapshot: dict) -> None:
        inv = self.load_inventory()
        for p in inv.get("projects", []):
            if p["id"] == project_id:
                p.update(snapshot)
                self.save_inventory_atomic(inv)
                return
        snapshot["id"] = project_id
        inv.setdefault("projects", []).append(snapshot)
        self.save_inventory_atomic(inv)

    def get_machine(self, machine_id: str) -> dict | None:
        inv = self.load_inventory()
        for m in inv.get("machines", []):
            if m["id"] == machine_id:
                return m
        return None

    def get_project(self, project_id: str) -> dict | None:
        inv = self.load_inventory()
        for p in inv.get("projects", []):
            if p["id"] == project_id:
                return p
        return None

    def _default(self) -> dict:
        return {
            "schema_version": 1,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "machines": [],
            "projects": [],
            "providers": [],
            "keys": [],
            "models": [],
        }
