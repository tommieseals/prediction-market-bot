"""
smart_click.py - Vision-based UI element finder and clicker.

Uses Clawdbot's local gateway (/v1/responses) to analyze a screenshot and find
where a described UI element is, then clicks it.

Usage:
  python smart_click.py "Approve plan button"
  python smart_click.py "Submit button" output_screenshot=C:/Users/User/clawd/after-click.png
  python smart_click.py "Connect button in the toolbar" wait=2
  python smart_click.py "Submit button" dry_run=true
  python smart_click.py "Submit button" find_only=true
"""

import sys
import json
import time
import base64
import io

GATEWAY_URL = "http://localhost:18789"
GATEWAY_TOKEN = "2d6d6076846afc70bcd6035e8d1c4405fda0fa2ced66a0a8bd3789b1b9280c7f"
MODEL = "claude-opus-4-5"


def take_screenshot():
    """Take a full desktop screenshot and return as base64 PNG string."""
    import pyautogui
    from PIL import Image
    pyautogui.FAILSAFE = False

    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode(), img.width, img.height


def find_element(description, screenshot_b64, width, height):
    """
    Ask Claude (via Clawdbot gateway) to find the described UI element.
    Returns parsed JSON result dict with 'found', 'x', 'y', 'description'.
    """
    import urllib.request

    prompt = (
        f"Look at this screenshot of a desktop ({width}x{height} pixels). "
        f"Find the UI element described as: \"{description}\". "
        f"Return ONLY a JSON object with the pixel coordinates of its CENTER:\n"
        f"{{\"x\": <number>, \"y\": <number>, \"found\": true, \"description\": \"<what you found>\"}}\n"
        f"If not found: {{\"x\": null, \"y\": null, \"found\": false, \"description\": \"<what you see>\"}}\n"
        f"No other text — just the JSON."
    )

    payload = {
        "model": MODEL,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {
                        "type": "input_text",
                        "text": prompt,
                    },
                ],
            }
        ],
        "max_output_tokens": 256,
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{GATEWAY_URL}/v1/responses",
        data=data,
        headers={
            "Authorization": f"Bearer {GATEWAY_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())

    # Extract text from response
    raw = ""
    for item in body.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    raw += part.get("text", "")

    raw = raw.strip()

    # Strip markdown code fences if present
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except Exception:
                continue

    return json.loads(raw)


def smart_click(description, output_screenshot=None, wait=1.5, dry_run=False):
    """Find and click a UI element described in natural language."""
    import pyautogui
    pyautogui.FAILSAFE = False

    # Take screenshot
    print(json.dumps({"status": "Taking screenshot..."}))
    screenshot_b64, width, height = take_screenshot()

    # Ask Claude where the element is
    print(json.dumps({"status": f"Asking Claude to find: {description}"}))
    result = find_element(description, screenshot_b64, width, height)

    if not result.get("found"):
        print(json.dumps({
            "error": "Element not found",
            "description": result.get("description", "unknown"),
            "query": description
        }))
        return

    x, y = result["x"], result["y"]
    print(json.dumps({
        "found": True,
        "element": result.get("description"),
        "coordinates": {"x": x, "y": y},
        "query": description
    }))

    if dry_run:
        print(json.dumps({"dry_run": True, "would_click": {"x": x, "y": y}}))
        return

    # Click
    pyautogui.click(x, y)
    print(json.dumps({"clicked": {"x": x, "y": y}}))

    # Wait
    time.sleep(float(wait))

    # Screenshot after click
    save_path = output_screenshot or "C:/Users/User/clawd/smart-click-result.png"
    img = pyautogui.screenshot()
    img.save(save_path)
    print(json.dumps({"screenshot": save_path}))


def find_only(description):
    """Just find an element and return coordinates without clicking."""
    print(json.dumps({"status": "Taking screenshot..."}))
    screenshot_b64, width, height = take_screenshot()
    print(json.dumps({"status": f"Asking Claude to find: {description}"}))
    result = find_element(description, screenshot_b64, width, height)
    print(json.dumps(result))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({
            "usage": "python smart_click.py <description> [output_screenshot=path] [wait=seconds] [dry_run=true] [find_only=true]"
        }))
        sys.exit(0)

    description = sys.argv[1]

    kwargs = {}
    for a in sys.argv[2:]:
        if "=" in a:
            k, v = a.split("=", 1)
            kwargs[k] = v

    if kwargs.get("find_only", "").lower() == "true":
        find_only(description)
    else:
        smart_click(
            description,
            output_screenshot=kwargs.get("output_screenshot"),
            wait=float(kwargs.get("wait", 1.5)),
            dry_run=kwargs.get("dry_run", "").lower() == "true",
        )
