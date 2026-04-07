"""
extension_click.py - Click buttons inside Chrome extension pages via CDP.

Injects JavaScript directly into the Claude extension sidepanel, bypassing
OS-level mouse events which don't reliably hit extension renderer pages.

Usage:
  python extension_click.py "Approve plan"
  python extension_click.py "Make changes"
  python extension_click.py list                  # list all buttons in sidepanel
  python extension_click.py js "document.title"   # run arbitrary JS
"""

import sys
import json
import time
import urllib.request
import websocket  # pip install websocket-client


CDP_HOST = "http://localhost:9223"
EXTENSION_ID = "fcoeoabgfenejglbffodgkkbkcdhcgfn"


def get_targets():
    with urllib.request.urlopen(f"{CDP_HOST}/json") as r:
        return json.loads(r.read())


def get_sidepanel_ws_url():
    """Return WebSocket debugger URL for the active Claude sidepanel."""
    targets = get_targets()
    panels = [
        t for t in targets
        if t.get("type") == "page"
        and EXTENSION_ID in t.get("url", "")
        and "sidepanel" in t.get("url", "")
        and t.get("webSocketDebuggerUrl")
    ]
    if not panels:
        return None, "No Claude sidepanel target found"
    # Pick the last one (most recently active)
    return panels[-1]["webSocketDebuggerUrl"], None


def cdp_eval(ws_url, expression, timeout=10):
    """Execute JavaScript in a CDP target via WebSocket and return the result."""
    ws = websocket.create_connection(ws_url, timeout=timeout)
    try:
        cmd = json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": False,
            }
        })
        ws.send(cmd)
        raw = ws.recv()
        result = json.loads(raw)
        return result.get("result", {}).get("result", {})
    finally:
        ws.close()


def list_buttons(ws_url):
    """List all visible buttons in the sidepanel."""
    js = """
(function() {
    var buttons = Array.from(document.querySelectorAll('button, [role="button"], input[type="button"], input[type="submit"], a[href]'));
    return buttons.map(function(b) {
        var text = (b.innerText || b.textContent || b.value || b.getAttribute('aria-label') || '').trim();
        var rect = b.getBoundingClientRect();
        return {
            text: text.slice(0, 80),
            tag: b.tagName,
            visible: rect.width > 0 && rect.height > 0,
            x: Math.round(rect.x + rect.width/2),
            y: Math.round(rect.y + rect.height/2)
        };
    }).filter(function(b) { return b.visible && b.text; });
})()
"""
    return cdp_eval(ws_url, js)


def click_button_by_text(ws_url, text):
    """
    Find a button whose text contains `text` (case-insensitive) and click it.
    Returns info about what was clicked.
    """
    # Escape for JS string
    text_js = text.replace("\\", "\\\\").replace("'", "\\'")
    js = f"""
(function() {{
    var search = '{text_js}'.toLowerCase();
    var candidates = Array.from(document.querySelectorAll('button, [role="button"], input[type="button"], input[type="submit"]'));
    var match = candidates.find(function(b) {{
        var t = (b.innerText || b.textContent || b.value || b.getAttribute('aria-label') || '').trim().toLowerCase();
        return t.includes(search);
    }});
    if (!match) return {{ found: false, searched: search }};
    var rect = match.getBoundingClientRect();
    // Dispatch both mousedown + click for maximum compatibility
    ['mousedown', 'mouseup', 'click'].forEach(function(evtType) {{
        var evt = new MouseEvent(evtType, {{ bubbles: true, cancelable: true, view: window }});
        match.dispatchEvent(evt);
    }});
    // Also call .click() directly
    match.click();
    return {{
        found: true,
        text: (match.innerText || match.textContent || '').trim().slice(0, 80),
        tag: match.tagName,
        x: Math.round(rect.x + rect.width/2),
        y: Math.round(rect.y + rect.height/2)
    }};
}})()
"""
    return cdp_eval(ws_url, js)


def run_js(ws_url, expression):
    return cdp_eval(ws_url, expression)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"usage": "python extension_click.py <button-text|list|js> [expression]"}))
        sys.exit(0)

    command = sys.argv[1]

    ws_url, err = get_sidepanel_ws_url()
    if err:
        print(json.dumps({"error": err}))
        sys.exit(1)

    print(json.dumps({"sidepanel": ws_url.split("/")[-1][:40]}))

    if command == "list":
        result = list_buttons(ws_url)
        buttons = result.get("value", [])
        print(json.dumps({"buttons": buttons, "count": len(buttons)}))

    elif command == "js":
        expr = sys.argv[2] if len(sys.argv) > 2 else "document.title"
        result = run_js(ws_url, expr)
        print(json.dumps({"result": result}))

    else:
        # Treat as button text to click
        result = click_button_by_text(ws_url, command)
        val = result.get("value", {})
        if isinstance(val, dict):
            print(json.dumps(val))
        else:
            print(json.dumps({"raw": result}))
