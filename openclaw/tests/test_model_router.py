from pathlib import Path

from openclaw.model_router import ModelRouter
from openclaw.quota_ledger import QuotaLedger


def test_monitoring_plan_prefers_free_ollama(tmp_path):
    router = ModelRouter(QuotaLedger(path=Path(tmp_path) / "keys.json"))

    plan = router.get_candidate_plan(task_type="monitoring", max_cost="free", quality="standard")

    assert plan
    assert plan[0]["provider"] == "ollama"
    assert all(candidate["cost_tier"] == "free" for candidate in plan)


def test_local_route_maps_to_jarvis_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("OGE_RUNTIME_MACHINE", "jarvis")
    router = ModelRouter(QuotaLedger(path=Path(tmp_path) / "keys.json"))

    plan = router.get_candidate_plan(task_type="monitoring", max_cost="free", quality="standard")

    assert plan[0]["machine"] == "jarvis"
    assert plan[0]["model"] == "qwen2.5:14b"


def test_route_falls_back_to_mixed_when_free_routes_fail(tmp_path, monkeypatch):
    ledger = QuotaLedger(path=Path(tmp_path) / "keys.json")
    router = ModelRouter(ledger)

    def fake_execute(candidate, prompt, timeout_seconds, task_type):
        if candidate["provider"] == "ollama":
            raise RuntimeError("ollama unavailable")
        return "gateway response", 0

    monkeypatch.setattr(router, "_execute_candidate", fake_execute)

    result = router.route_with_metadata(
        "Find me the best next move",
        task_type="research",
        max_cost="free",
        quality="high",
    )

    assert result["text"] == "gateway response"
    assert result["decision"]["provider"] == "clawdbot"
    summary = ledger.get_routing_summary()
    assert summary["providers"]["clawdbot"]["successes"] == 1
    assert summary["providers"]["ollama"]["failures"] >= 1


def test_self_hosted_route_resolves_to_localhost(tmp_path, monkeypatch):
    monkeypatch.setenv("OGE_RUNTIME_MACHINE", "jarvis")
    router = ModelRouter(QuotaLedger(path=Path(tmp_path) / "keys.json"))

    plan = router.get_candidate_plan(task_type="analysis", max_cost="free", quality="high")
    jarvis_routes = [candidate for candidate in plan if candidate["machine"] == "jarvis"]

    assert jarvis_routes
    assert all(candidate["host"] == "127.0.0.1" for candidate in jarvis_routes)


def test_discover_clawdbot_binary_uses_known_mac_path(tmp_path, monkeypatch):
    fake_home = Path(tmp_path)
    binary = fake_home / ".npm-global" / "bin" / "clawdbot"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n")

    monkeypatch.setattr("openclaw.model_router.shutil.which", lambda name: None)
    monkeypatch.setattr("openclaw.model_router.Path.home", lambda: fake_home)
    monkeypatch.delenv("CLAWDBOT_BIN", raising=False)

    assert ModelRouter._discover_clawdbot_binary() == str(binary)


def test_discover_node_binary_uses_known_mac_path(tmp_path, monkeypatch):
    fake_node = Path(tmp_path) / "node"
    fake_node.write_text("#!/bin/sh\n")

    monkeypatch.setattr("openclaw.model_router.shutil.which", lambda name: None)
    monkeypatch.setenv("NODE_BIN", str(fake_node))

    assert ModelRouter._discover_node_binary() == str(fake_node)


def test_long_analysis_prompt_prioritizes_fast_local_route(tmp_path, monkeypatch):
    monkeypatch.setenv("OGE_RUNTIME_MACHINE", "jarvis")
    router = ModelRouter(QuotaLedger(path=Path(tmp_path) / "keys.json"))

    plan = router.get_candidate_plan(task_type="analysis", max_cost="mixed", quality="high")
    prioritized = router._prioritize_candidates(plan, "x" * 1500, "analysis")

    assert prioritized[0]["route_id"] == "ollama_local_fast"
    assert prioritized[1]["route_id"] == "clawdbot_gateway"


def test_build_ollama_request_compacts_analysis_fast_route():
    prompt = "word " * 500
    normalized, num_predict, timeout_cap = ModelRouter._build_ollama_request(
        {"route_id": "ollama_local_fast", "model": "qwen2.5:7b", "host": "127.0.0.1"},
        prompt,
        timeout_seconds=90,
        task_type="analysis",
    )

    assert len(normalized) <= 700
    assert num_predict == 96
    assert timeout_cap == 30
