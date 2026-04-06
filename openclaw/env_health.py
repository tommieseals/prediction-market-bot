"""OpenClaw Anomaly — Environment Health Checks.

First-party telemetry: Docker, network/Tailscale, disk, GPU.
Trusted and actionable immediately (no quarantine needed).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config


class EnvHealth:
    """Infrastructure health checks for the workspace."""

    def check_all(self) -> dict:
        """Run all health checks. Returns structured report."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "docker": self.check_docker(),
            "network": self.check_network(),
            "storage": self.check_storage(),
            "services": self.check_services(),
        }

    def check_docker(self) -> dict:
        """Check Docker daemon and running containers."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return {"status": "error", "message": result.stderr.strip()[:200]}
            containers = []
            for line in result.stdout.strip().split("\n"):
                if "\t" in line:
                    name, status = line.split("\t", 1)
                    containers.append({"name": name, "status": status})
            return {"status": "ok", "containers": containers, "count": len(containers)}
        except FileNotFoundError:
            return {"status": "not_installed", "message": "Docker not found"}
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "message": "Docker command timed out"}
        except OSError as e:
            return {"status": "error", "message": str(e)[:200]}

    def check_network(self) -> dict:
        """Check network connectivity to key machines."""
        targets = {
            "jarvis": "100.89.75.126",
            "tom": "100.88.105.106",
            "rtx": "100.115.12.91",
        }
        results = {}
        for name, ip in targets.items():
            try:
                import platform
                system = platform.system()
                if system == "Windows":
                    cmd = ["ping", "-n", "1", "-w", "3000", ip]
                elif system == "Darwin":
                    cmd = ["ping", "-c", "1", "-W", "3000", ip]
                else:
                    cmd = ["ping", "-c", "1", "-w", "3", ip]
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=5,
                )
                results[name] = "reachable" if proc.returncode == 0 else "unreachable"
            except (subprocess.TimeoutExpired, OSError):
                results[name] = "error"
        return {"status": "ok", "hosts": results}

    def check_storage(self) -> dict:
        """Check available disk space."""
        try:
            usage = shutil.disk_usage(str(Config.BASE_DIR))
            pct_used = (usage.used / usage.total) * 100
            return {
                "status": "ok",
                "total_gb": round(usage.total / (1024 ** 3), 1),
                "used_gb": round(usage.used / (1024 ** 3), 1),
                "free_gb": round(usage.free / (1024 ** 3), 1),
                "pct_used": round(pct_used, 1),
                "warning": pct_used > 90,
            }
        except OSError as e:
            return {"status": "error", "message": str(e)[:200]}

    def check_services(self) -> dict:
        """Check key service endpoints (ClawdBot gateway, etc.)."""
        services = {}
        # Check ClawdBot gateway
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(("127.0.0.1", Config.CLAWDBOT_GATEWAY_PORT))
            services["clawdbot_gateway"] = "up" if result == 0 else "down"
            sock.close()
        except OSError:
            services["clawdbot_gateway"] = "error"
        return {"status": "ok", "services": services}
