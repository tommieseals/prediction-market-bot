"""Model routing for OpenClaw/Anomaly Bot.

Safer integration v2:
- Keep the current Clawdbot gateway path for managed/provider-backed calls.
- Burn free local Ollama capacity first when it is a good fit.
- Record routing decisions so the dashboard and audits can explain behavior.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import requests

from openclaw.config import Config
from openclaw.quota_ledger import QuotaLedger


@dataclass
class RouteDecision:
    route_id: str
    provider: str
    model: str
    machine: str
    cost_tier: str
    quality: str
    reason: str
    task_type: str
    max_cost: str


class ModelRouter:
    """Route prompts across verified local backends before paid fallbacks."""

    def __init__(self, quota_ledger: QuotaLedger | None = None):
        self.quota = quota_ledger or QuotaLedger()

    def get_candidate_plan(
        self,
        task_type: str = "general",
        max_cost: str = "free",
        quality: str = "standard",
        model: str | None = None,
    ) -> list[dict]:
        """Return ordered route candidates without executing them."""
        route_ids = list(Config.TASK_ROUTE_PREFERENCES.get(task_type, Config.TASK_ROUTE_PREFERENCES["general"]))
        candidates: list[dict] = []

        if model and not model.startswith("openai/"):
            for route_id in ("ollama_local_reasoning", "ollama_jarvis_reasoning", "ollama_tom_reasoning"):
                route = dict(Config.MODEL_PROVIDER_CATALOG[route_id])
                route["route_id"] = route_id
                route["model"] = model
                route["reason"] = f"Explicit model override for task_type={task_type}"
                candidates.append(route)

        for route_id in route_ids:
            route = Config.MODEL_PROVIDER_CATALOG.get(route_id)
            if not route:
                continue
            route = self._resolve_route(dict(route))
            route["route_id"] = route_id
            route["reason"] = self._build_reason(route_id, task_type, quality)
            if self._cost_allowed(route["cost_tier"], max_cost):
                candidates.append(route)

        if not candidates and max_cost != "paid":
            return self.get_candidate_plan(task_type=task_type, max_cost="paid", quality=quality, model=model)
        return self._dedupe_candidates(candidates)

    def route(
        self,
        prompt: str,
        task_type: str = "general",
        max_cost: str = "free",
        quality: str = "standard",
        model: str | None = None,
        timeout_seconds: int = 45,
    ) -> str:
        result = self.route_with_metadata(
            prompt=prompt,
            task_type=task_type,
            max_cost=max_cost,
            quality=quality,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        return result["text"]

    def route_with_metadata(
        self,
        prompt: str,
        task_type: str = "general",
        max_cost: str = "free",
        quality: str = "standard",
        model: str | None = None,
        timeout_seconds: int = 45,
    ) -> dict:
        """Execute the first working route and return text plus decision metadata."""
        plans = [(max_cost, self._prioritize_candidates(self.get_candidate_plan(task_type, max_cost, quality, model), prompt, task_type))]
        if max_cost == "free":
            plans.append(("mixed", self._prioritize_candidates(self.get_candidate_plan(task_type, "mixed", quality, model), prompt, task_type)))

        failures: list[dict] = []
        for planned_cost, plan in plans:
            for candidate in plan:
                started = time.perf_counter()
                try:
                    response, tokens_used = self._execute_candidate(candidate, prompt, timeout_seconds, task_type)
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    if response:
                        decision = RouteDecision(
                            route_id=candidate["route_id"],
                            provider=candidate["provider"],
                            model=candidate["model"],
                            machine=candidate["machine"],
                            cost_tier=candidate["cost_tier"],
                            quality=candidate["quality"],
                            reason=candidate["reason"],
                            task_type=task_type,
                            max_cost=planned_cost,
                        )
                        self.quota.record_route_decision(
                            provider=decision.provider,
                            model=decision.model,
                            task_type=task_type,
                            route_id=decision.route_id,
                            cost_tier=decision.cost_tier,
                            success=True,
                            latency_ms=latency_ms,
                            details={"machine": decision.machine, "reason": decision.reason},
                        )
                        if tokens_used:
                            self.quota.record_usage_event(
                                provider=decision.provider,
                                key_label=f"{decision.provider}_{decision.model}",
                                tokens_used=tokens_used,
                                requests_used=1,
                            )
                        return {
                            "text": response,
                            "decision": decision.__dict__,
                            "failures": failures,
                        }
                except Exception as exc:
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    failures.append({
                        "route_id": candidate["route_id"],
                        "provider": candidate["provider"],
                        "error": str(exc),
                    })
                    self.quota.record_route_decision(
                        provider=candidate["provider"],
                        model=candidate["model"],
                        task_type=task_type,
                        route_id=candidate["route_id"],
                        cost_tier=candidate["cost_tier"],
                        success=False,
                        latency_ms=latency_ms,
                        details={"machine": candidate["machine"], "error": str(exc)},
                    )

        stub = f"[ModelRouter unavailable - no successful route for {task_type}: {prompt[:80]}]"
        return {
            "text": stub,
            "decision": {
                "route_id": "stub",
                "provider": "none",
                "model": "none",
                "machine": "none",
                "cost_tier": max_cost,
                "quality": quality,
                "reason": "all routes failed",
                "task_type": task_type,
                "max_cost": max_cost,
            },
            "failures": failures,
        }

    def burn_free_quota(self) -> dict:
        """Suggest productive work when free/mixed budget is sitting idle."""
        routing = self.quota.recommend_routing()
        trigger = any(
            rec.get("type") == "unused_capacity"
            for rec in routing.get("recommendations", [])
        )
        suggestions = []
        if trigger:
            suggestions = [
                {"task_type": "monitoring", "goal": "refresh health probes and update action queue"},
                {"task_type": "research", "goal": "collect top 3 framework/tool changes"},
                {"task_type": "absorption", "goal": "scan provider blogs and quarantine candidates"},
            ]
        free_routes = [
            {
                "route_id": route_id,
                "provider": resolved["provider"],
                "model": resolved["model"],
                "machine": resolved["machine"],
                "available": self._candidate_is_reachable(resolved),
            }
            for route_id, route in Config.MODEL_PROVIDER_CATALOG.items()
            for resolved in [self._resolve_route(dict(route))]
            if resolved.get("cost_tier") == "free" and resolved.get("provider") == "ollama"
        ]
        return {
            "triggered": trigger,
            "recommendations": routing.get("recommendations", []),
            "suggested_tasks": suggestions,
            "free_routes": free_routes,
        }

    def routing_report(self) -> dict:
        return {
            "brand": Config.BRAND_NAME,
            "summary": self.quota.get_routing_summary(),
            "burn_plan": self.burn_free_quota(),
        }

    def _execute_candidate(
        self,
        candidate: dict,
        prompt: str,
        timeout_seconds: int,
        task_type: str,
    ) -> tuple[str | None, int]:
        provider = candidate["provider"]
        if provider == "ollama":
            return self._call_ollama(candidate, prompt, timeout_seconds, task_type)
        if provider == "clawdbot":
            return self._call_clawdbot(prompt, timeout_seconds), 0
        raise RuntimeError(f"Provider not directly executable yet: {provider}")

    def _call_ollama(
        self,
        candidate: dict,
        prompt: str,
        timeout_seconds: int,
        task_type: str,
    ) -> tuple[str | None, int]:
        host = candidate["host"]
        port = candidate["port"]
        model = candidate["model"]
        normalized_prompt, num_predict, request_timeout = self._build_ollama_request(
            candidate,
            prompt,
            timeout_seconds,
            task_type,
        )

        with socket.create_connection((host, port), timeout=1.5):
            pass

        response = requests.post(
            f"http://{host}:{port}/api/generate",
            json={
                "model": model,
                "prompt": normalized_prompt,
                "stream": False,
                "options": {"num_predict": num_predict},
            },
            timeout=request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        text = (data.get("response") or "").strip()
        tokens_used = int(data.get("eval_count", 0) + data.get("prompt_eval_count", 0))
        if not text:
            raise RuntimeError(f"Ollama route {candidate['route_id']} returned empty text")
        return text, tokens_used

    def _call_clawdbot(self, prompt: str, timeout_seconds: int) -> str:
        normalized_prompt = _normalize_prompt(prompt, max_chars=2500)
        clawdbot_bin = self._discover_clawdbot_binary()
        if not clawdbot_bin:
            raise FileNotFoundError("clawdbot binary not found")
        node_bin = self._discover_node_binary()

        session_id = f"anomaly-router-{uuid.uuid4().hex[:12]}"
        if clawdbot_bin.lower().endswith((".cmd", ".bat")):
            command = (
                f'"{clawdbot_bin}" agent --agent {Config.CLAWDBOT_PRIMARY_AGENT} '
                f'--session-id {session_id} --thinking minimal --timeout 120 '
                f'--message {json.dumps(normalized_prompt)} --json'
            )
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                encoding="utf-8",
                errors="replace",
                shell=True,
            )
        else:
            launch = [clawdbot_bin]
            if node_bin:
                launch = [node_bin, clawdbot_bin]
            proc = subprocess.run(
                launch + [
                    "agent",
                    "--agent",
                    Config.CLAWDBOT_PRIMARY_AGENT,
                    "--session-id",
                    session_id,
                    "--thinking",
                    "minimal",
                    "--timeout",
                    "120",
                    "--message",
                    normalized_prompt,
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                encoding="utf-8",
                errors="replace",
            )
        payload = _extract_json_payload(proc.stdout) or _extract_json_payload(proc.stderr)
        if proc.returncode != 0 or not payload:
            raise RuntimeError(
                f"clawdbot returned {proc.returncode}: "
                f"stdout={proc.stdout[:160]!r} stderr={proc.stderr[:160]!r}"
            )
        texts = payload.get("result", {}).get("payloads", [])
        reply = ((texts[0].get("text") if texts else "") or "").strip()
        if not reply:
            raise RuntimeError("clawdbot returned no text payload")
        return reply

    def _candidate_is_reachable(self, candidate: dict) -> bool:
        if candidate.get("provider") != "ollama":
            return True
        try:
            with socket.create_connection((candidate["host"], candidate["port"]), timeout=0.5):
                return True
        except OSError:
            return False

    @staticmethod
    def _resolve_route(route: dict) -> dict:
        """Map local routes onto the actual runtime host/model inventory."""
        if route.get("provider") != "ollama":
            return route

        runtime = Config.get_runtime_machine()
        if route.get("machine") == "local":
            profile = Config.get_local_ollama_profile()
            route["machine"] = str(profile["machine"])
            route["host"] = str(profile["host"])
            route["port"] = int(profile["port"])
            if route.get("model") == "gemma4:e4b":
                route["model"] = str(profile["reasoning_model"])
            elif route.get("model") == "qwen3:4b":
                route["model"] = str(profile["fast_model"])
            return route

        if route.get("machine") == runtime:
            route["host"] = "127.0.0.1"
        return route

    @staticmethod
    def _discover_clawdbot_binary() -> str | None:
        candidates = [
            shutil.which("clawdbot"),
            shutil.which("clawdbot.cmd"),
            os.getenv("CLAWDBOT_BIN"),
            str(Path.home() / ".npm-global" / "bin" / "clawdbot"),
            str(Path("/opt/homebrew/bin/clawdbot")),
            str(Path("/usr/local/bin/clawdbot")),
            str(Path.home() / "AppData" / "Roaming" / "npm" / "clawdbot.cmd"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return None

    @staticmethod
    def _prioritize_candidates(candidates: list[dict], prompt: str, task_type: str) -> list[dict]:
        if task_type not in {"analysis", "self_thought"} or len(prompt) <= 1200:
            return candidates

        preferred_order = {
            "ollama_local_fast": 0,
            "clawdbot_gateway": 1,
            "ollama_local_reasoning": 2,
        }
        indexed = list(enumerate(candidates))
        indexed.sort(key=lambda item: (preferred_order.get(item[1].get("route_id"), 50), item[0]))
        return [candidate for _, candidate in indexed]

    @staticmethod
    def _build_ollama_request(
        candidate: dict,
        prompt: str,
        timeout_seconds: int,
        task_type: str,
    ) -> tuple[str, int, int]:
        route_id = candidate.get("route_id", "")
        model = candidate.get("model", "")
        local_host = candidate.get("host") in {"127.0.0.1", "localhost"}

        max_chars = 2000
        num_predict = 300
        timeout_cap = 45 if local_host else 20

        if task_type == "health_check":
            max_chars = 500
            num_predict = 48
            timeout_cap = 20 if local_host else 15
        elif task_type in {"analysis", "self_thought"}:
            if route_id == "ollama_local_fast" or model in {"qwen2.5:7b", "qwen3:4b", "gemma4:e4b"}:
                max_chars = 700
                num_predict = 96
                timeout_cap = 30 if local_host else 20
            else:
                max_chars = 1100
                num_predict = 220
                timeout_cap = 45 if local_host else 20
        elif task_type == "research":
            max_chars = 1200
            num_predict = 180
            timeout_cap = 45 if local_host else 20

        return _normalize_prompt(prompt, max_chars=max_chars), num_predict, min(timeout_seconds, timeout_cap)

    @staticmethod
    def _discover_node_binary() -> str | None:
        candidates = [
            shutil.which("node"),
            os.getenv("NODE_BIN"),
            str(Path("/usr/local/bin/node")),
            str(Path("/opt/homebrew/bin/node")),
            str(Path.home() / "AppData" / "Program Files" / "nodejs" / "node.exe"),
            str(Path.home() / "AppData" / "Roaming" / "nvm" / "node.exe"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return None

    @staticmethod
    def _build_reason(route_id: str, task_type: str, quality: str) -> str:
        if route_id == "clawdbot_gateway":
            return (
                "Preserve live provider auth, cooldown logic, and tool bridge for "
                f"{task_type} requests."
            )
        if quality == "high" and "jarvis" in route_id:
            return f"Prefer stronger free reasoning for {task_type}."
        if "fast" in route_id:
            return f"Prefer low-latency free model for {task_type}."
        return f"Burn free local/mesh capacity first for {task_type}."

    @staticmethod
    def _cost_allowed(candidate_cost: str, max_cost: str) -> bool:
        return Config.ROUTE_COST_ORDER[candidate_cost] <= Config.ROUTE_COST_ORDER[max_cost]

    @staticmethod
    def _dedupe_candidates(candidates: list[dict]) -> list[dict]:
        seen: set[tuple[str, str, str]] = set()
        unique: list[dict] = []
        for candidate in candidates:
            key = (candidate["provider"], candidate["machine"], candidate["model"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique


def _normalize_prompt(prompt: str, max_chars: int) -> str:
    compact = " ".join(prompt.split())
    return compact[:max_chars] if len(compact) > max_chars else compact


def _extract_json_payload(raw: str | None) -> dict | None:
    if not raw:
        return None
    cleaned = raw.lstrip("\ufeff\r\n\t ")
    candidates = [cleaned]
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidates.append(cleaned[first:last + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None
