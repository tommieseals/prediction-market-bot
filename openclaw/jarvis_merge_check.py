"""Jarvis-first merge readiness report.

Run this before or after deployment to verify that OpenClaw is pointed at the
Mac Pro as the sovereign control plane and that Tom/RTX remain worker surfaces.
"""
from __future__ import annotations

import json
import socket
from datetime import datetime, timezone

from openclaw.config import Config
from openclaw.env_health import EnvHealth
from openclaw.model_router import ModelRouter


def _tcp_reachable(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def build_report() -> dict:
    local_profile = Config.get_local_ollama_profile()
    router = ModelRouter()
    health_plan = router.get_candidate_plan(task_type="health_check", max_cost="free")
    strategic_plan = router.get_candidate_plan(task_type="strategic", max_cost="mixed", quality="high")
    env_health = EnvHealth().check_services()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "brand": Config.BRAND_NAME,
        "runtime_machine": Config.get_runtime_machine(),
        "control_plane": {
            "owner_agent": Config.OGE_CONTROLLER,
            "gateway_host": Config.CLAWDBOT_GATEWAY_HOST,
            "gateway_port": Config.CLAWDBOT_GATEWAY_PORT,
            "jarvis_target_matches": (
                Config.CLAWDBOT_GATEWAY_HOST == Config.JARVIS_HOST
                and Config.CLAWDBOT_GATEWAY_PORT == 18790
            ),
            "reachable": _tcp_reachable(Config.CLAWDBOT_GATEWAY_HOST, Config.CLAWDBOT_GATEWAY_PORT),
        },
        "runtime_local_ollama": local_profile,
        "managed_agents": Config.MANAGED_AGENTS,
        "observed_agents": Config.OBSERVED_AGENTS,
        "health_check_plan": [
            {"route_id": route["route_id"], "provider": route["provider"], "machine": route["machine"], "model": route["model"]}
            for route in health_plan[:4]
        ],
        "strategic_plan": [
            {"route_id": route["route_id"], "provider": route["provider"], "machine": route["machine"], "model": route["model"]}
            for route in strategic_plan[:4]
        ],
        "service_health": env_health.get("services", {}),
        "ready_for_merge": (
            Config.OGE_CONTROLLER == "jarvis"
            and Config.MANAGED_AGENTS == ["jarvis"]
            and Config.CLAWDBOT_GATEWAY_HOST == Config.JARVIS_HOST
        ),
    }


def main() -> None:
    print(json.dumps(build_report(), indent=2))


if __name__ == "__main__":
    main()
