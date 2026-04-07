from openclaw.env_health import EnvHealth


class TestEnvHealth:
    def test_docker_not_installed_is_optional(self, monkeypatch):
        def boom(*args, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr("subprocess.run", boom)
        result = EnvHealth().check_docker()
        assert result["status"] == "ok"
        assert result["available"] is False

    def test_service_check_uses_configured_gateway_host(self, monkeypatch):
        captured = {}

        class FakeSocket:
            def settimeout(self, timeout):
                captured["timeout"] = timeout

            def connect_ex(self, target):
                captured["target"] = target
                return 0

            def close(self):
                captured["closed"] = True

        monkeypatch.setattr("socket.socket", lambda *args, **kwargs: FakeSocket())

        result = EnvHealth().check_services()

        assert result["services"]["clawdbot_gateway"] == "up"
        assert captured["target"] == ("100.89.75.126", 18790)
        assert result["services"]["control_plane"] == "jarvis"
