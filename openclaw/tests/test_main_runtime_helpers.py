from unittest.mock import patch

from openclaw.main import _extract_json_payload, _normalize_prompt, _telegram_send


def test_normalize_prompt_collapses_whitespace():
    prompt = "Line one\n\nLine\t two   with   spaces"
    assert _normalize_prompt(prompt, max_chars=200) == "Line one Line two with spaces"


def test_extract_json_payload_handles_banner_noise():
    raw = 'warning: something happened\n{"status": "ok", "result": {"payloads": []}}\n'
    payload = _extract_json_payload(raw)
    assert payload is not None
    assert payload["status"] == "ok"


def test_telegram_send_direct_mode_skips_gateway():
    with patch("openclaw.main._audit"), \
         patch("openclaw.main.Config.get_telegram_delivery_mode", return_value="direct"), \
         patch("openclaw.main._send_via_gateway") as gateway_send, \
         patch("openclaw.main._send_via_direct_api", return_value=True) as direct_send:
        _telegram_send("hello world")

    gateway_send.assert_not_called()
    direct_send.assert_called_once()


def test_telegram_send_gateway_mode_uses_gateway_first():
    with patch("openclaw.main._audit"), \
         patch("openclaw.main.Config.get_telegram_delivery_mode", return_value="gateway"), \
         patch("openclaw.main._send_via_gateway", return_value=True) as gateway_send, \
         patch("openclaw.main._send_via_direct_api") as direct_send:
        _telegram_send("hello world")

    gateway_send.assert_called_once()
    direct_send.assert_not_called()
