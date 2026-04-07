"""
computer_use.py - Full desktop control for Clawdbot
Gives the AI agent the ability to see and interact with anything on screen.

Usage: python computer_use.py <command> [args]
"""

import sys
import json
import time
import argparse
import base64
import io
import os

def get_pyautogui():
    import pyautogui
    pyautogui.FAILSAFE = False  # Disable corner failsafe for automation
    pyautogui.PAUSE = 0.05
    return pyautogui

def screenshot(region=None, window_title=None, output_path=None):
    """Take a full desktop screenshot or specific window/region."""
    import pyautogui
    from PIL import Image
    pyautogui.FAILSAFE = False

    if window_title:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(window_title)
        if wins:
            w = wins[0]
            w.activate()
            time.sleep(0.3)
            region = (w.left, w.top, w.width, w.height)

    img = pyautogui.screenshot(region=region)

    # Downscale if too large (keep readable but not huge)
    max_w = 1920
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((max_w, int(img.height * ratio)))

    if output_path:
        img.save(output_path)
        result = {"saved": output_path, "size": f"{img.width}x{img.height}"}
    else:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        result = {"base64_png": b64, "size": f"{img.width}x{img.height}"}

    print(json.dumps(result))


def click(x, y, button="left", clicks=1, interval=0.1):
    """Click at screen coordinates."""
    pg = get_pyautogui()
    pg.click(int(x), int(y), button=button, clicks=int(clicks), interval=float(interval))
    print(json.dumps({"clicked": {"x": int(x), "y": int(y), "button": button, "clicks": int(clicks)}}))


def move(x, y, duration=0.2):
    """Move mouse to coordinates."""
    pg = get_pyautogui()
    pg.moveTo(int(x), int(y), duration=float(duration))
    print(json.dumps({"moved_to": {"x": int(x), "y": int(y)}}))


def drag(x1, y1, x2, y2, duration=0.5):
    """Drag from (x1,y1) to (x2,y2)."""
    pg = get_pyautogui()
    pg.moveTo(int(x1), int(y1))
    pg.dragTo(int(x2), int(y2), duration=float(duration), button="left")
    print(json.dumps({"dragged": {"from": [int(x1), int(y1)], "to": [int(x2), int(y2)]}}))


def type_text(text, interval=0.02):
    """Type text at the current cursor position."""
    pg = get_pyautogui()
    pg.typewrite(text, interval=float(interval))
    print(json.dumps({"typed": text}))


def write(text):
    """Write text (supports unicode, better than typewrite for special chars)."""
    pg = get_pyautogui()
    import pyperclip
    pyperclip.copy(text)
    pg.hotkey("ctrl", "v")
    time.sleep(0.1)
    print(json.dumps({"written": text}))


def hotkey(*keys):
    """Press a keyboard hotkey (e.g. ctrl c, alt tab, win d)."""
    pg = get_pyautogui()
    pg.hotkey(*keys)
    print(json.dumps({"hotkey": list(keys)}))


def keydown(key):
    """Press and release a single key."""
    pg = get_pyautogui()
    pg.press(key)
    print(json.dumps({"key": key}))


def scroll(x, y, amount):
    """Scroll at coordinates. Positive = up, negative = down."""
    pg = get_pyautogui()
    pg.moveTo(int(x), int(y))
    pg.scroll(int(amount))
    print(json.dumps({"scrolled": {"x": int(x), "y": int(y), "amount": int(amount)}}))


def position():
    """Get current mouse position."""
    pg = get_pyautogui()
    pos = pg.position()
    print(json.dumps({"x": pos.x, "y": pos.y}))


def screen_size():
    """Get screen dimensions."""
    pg = get_pyautogui()
    w, h = pg.size()
    print(json.dumps({"width": w, "height": h}))


def windows(title_filter=None):
    """List all open windows, optionally filtered by title."""
    import pygetwindow as gw
    all_wins = gw.getAllWindows()
    result = []
    for w in all_wins:
        if not w.title:
            continue
        if title_filter and title_filter.lower() not in w.title.lower():
            continue
        result.append({
            "title": w.title,
            "left": w.left, "top": w.top,
            "width": w.width, "height": w.height,
            "visible": w.visible,
            "active": w.isActive
        })
    print(json.dumps(result))


def activate_window(title):
    """Bring a window to the foreground by title (partial match)."""
    import pygetwindow as gw
    wins = [w for w in gw.getAllWindows() if title.lower() in w.title.lower() and w.visible]
    if not wins:
        print(json.dumps({"error": f"No visible window matching '{title}'"}))
        return
    w = wins[0]
    try:
        w.activate()
        time.sleep(0.3)
        print(json.dumps({"activated": w.title, "bounds": {"left": w.left, "top": w.top, "width": w.width, "height": w.height}}))
    except Exception as e:
        # Fallback: use Win32 API
        import ctypes
        ctypes.windll.user32.SetForegroundWindow(w._hWnd)
        time.sleep(0.3)
        print(json.dumps({"activated": w.title}))


def clipboard_get():
    """Get current clipboard content."""
    import pyperclip
    text = pyperclip.paste()
    print(json.dumps({"clipboard": text}))


def clipboard_set(text):
    """Set clipboard content."""
    import pyperclip
    pyperclip.copy(text)
    print(json.dumps({"clipboard_set": text}))


def find_image(image_path, confidence=0.8):
    """Find an image on screen and return its center coordinates."""
    pg = get_pyautogui()
    try:
        loc = pg.locateCenterOnScreen(image_path, confidence=float(confidence))
        if loc:
            print(json.dumps({"found": True, "x": loc.x, "y": loc.y}))
        else:
            print(json.dumps({"found": False}))
    except Exception as e:
        print(json.dumps({"found": False, "error": str(e)}))


def sleep(seconds):
    """Wait for specified seconds."""
    time.sleep(float(seconds))
    print(json.dumps({"slept": float(seconds)}))


def smart_click(description, output_screenshot=None, wait="1.5", dry_run="false"):
    """
    Vision-based click: ask Claude API to find a UI element by description and click it.
    Uses the Clawdbot auth token automatically.
    """
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smart_click.py")
    cmd = [sys.executable, script, description]
    if output_screenshot:
        cmd.append(f"output_screenshot={output_screenshot}")
    if wait:
        cmd.append(f"wait={wait}")
    if dry_run and dry_run.lower() == "true":
        cmd.append("dry_run=true")

    result = subprocess.run(cmd, capture_output=True, text=True)
    # Print each line of output as it came (each is a JSON status/result line)
    for line in (result.stdout + result.stderr).splitlines():
        line = line.strip()
        if line:
            try:
                json.loads(line)
                print(line)
            except Exception:
                print(json.dumps({"log": line}))


def extension_click(button_text_or_cmd, *extra_args):
    """
    Click a button inside the Claude Chrome extension sidepanel via CDP/JavaScript injection.
    More reliable than pyautogui for extension pages.
    Commands: 'list' (show all buttons), 'js <expr>' (eval JS), or button text to click.
    """
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extension_click.py")
    cmd = [sys.executable, script, button_text_or_cmd] + list(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    for line in (result.stdout + result.stderr).splitlines():
        line = line.strip()
        if line:
            try:
                json.loads(line)
                print(line)
            except Exception:
                print(json.dumps({"log": line}))


def run_workflow(steps_json):
    """Run a list of steps as a workflow: [{cmd, args}]"""
    steps = json.loads(steps_json)
    results = []
    for step in steps:
        cmd = step.get("cmd")
        args = step.get("args", [])
        kwargs = step.get("kwargs", {})
        try:
            fn = COMMANDS.get(cmd)
            if fn:
                # Capture stdout
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                fn(*args, **kwargs)
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout
                results.append({"cmd": cmd, "result": json.loads(output) if output.strip() else {}})
            else:
                results.append({"cmd": cmd, "error": "unknown command"})
        except Exception as e:
            results.append({"cmd": cmd, "error": str(e)})
        time.sleep(0.05)
    print(json.dumps({"workflow": results}))


COMMANDS = {
    "screenshot": screenshot,
    "click": click,
    "move": move,
    "drag": drag,
    "type": type_text,
    "write": write,
    "hotkey": hotkey,
    "key": keydown,
    "scroll": scroll,
    "position": position,
    "size": screen_size,
    "windows": windows,
    "activate": activate_window,
    "clipboard_get": clipboard_get,
    "clipboard_set": clipboard_set,
    "find": find_image,
    "sleep": sleep,
    "workflow": run_workflow,
    "smart_click": smart_click,
    "extension_click": extension_click,
}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"commands": list(COMMANDS.keys())}))
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    fn = COMMANDS.get(cmd)
    if not fn:
        print(json.dumps({"error": f"Unknown command '{cmd}'", "available": list(COMMANDS.keys())}))
        sys.exit(1)

    # Parse key=value kwargs from args
    positional = []
    kwargs = {}
    for a in args:
        if "=" in a and not a.startswith("-"):
            k, v = a.split("=", 1)
            kwargs[k] = v
        else:
            positional.append(a)

    try:
        fn(*positional, **kwargs)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
