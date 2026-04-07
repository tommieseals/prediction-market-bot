"""
One-shot script: activate Chrome, click Claude sidebar, type and send a message,
wait for response, save screenshot. Run as a single process to avoid focus loss.

Usage: python claude_sidebar_send.py "Your message here"
"""

import sys
import time
import json
import pyautogui
import pygetwindow as gw

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

SIDEBAR_INPUT_X = 1725
SIDEBAR_INPUT_Y = 912

def find_and_activate_chrome():
    import ctypes
    wins = [w for w in gw.getAllWindows()
            if 'chrome' in w.title.lower() and w.visible]
    if not wins:
        return None, "No Chrome window found"
    # Prefer windows with Claude in title, then any Chrome
    claude_wins = [w for w in wins if 'claude' in w.title.lower()]
    w = claude_wins[0] if claude_wins else wins[0]
    # Restore if minimized, then bring to front
    SW_RESTORE = 9
    ctypes.windll.user32.ShowWindow(w._hWnd, SW_RESTORE)
    time.sleep(0.4)
    ctypes.windll.user32.SetForegroundWindow(w._hWnd)
    time.sleep(0.6)
    return w, None

def send_to_claude_sidebar(message, output_screenshot=None, wait_seconds=6):
    # Step 1: Activate Chrome
    win, err = find_and_activate_chrome()
    if err:
        print(json.dumps({"error": err}))
        return

    # Step 2: Click the sidebar input
    pyautogui.click(SIDEBAR_INPUT_X, SIDEBAR_INPUT_Y)
    time.sleep(0.3)

    # Step 3: Clear any existing text
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)

    # Step 4: Type the message (character by character, no clipboard)
    pyautogui.typewrite(message, interval=0.03)
    time.sleep(0.2)

    # Step 5: Send
    pyautogui.press('enter')
    print(json.dumps({"sent": message}))

    # Step 6: Wait for response
    time.sleep(wait_seconds)

    # Step 7: Screenshot
    save_path = output_screenshot or 'C:/Users/User/clawd/claude-response.png'
    screenshot = pyautogui.screenshot()
    # Zoom the sidebar area
    from PIL import Image
    sidebar = screenshot.crop((1480, 0, 1920, 1080))
    sidebar_zoomed = sidebar.resize((880, 1080))
    sidebar_zoomed.save(save_path)
    print(json.dumps({"screenshot": save_path, "size": "880x1080"}))

if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "Hello! Can you summarize the current page?"
    out = sys.argv[2] if len(sys.argv) > 2 else None
    wait = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    send_to_claude_sidebar(msg, out, wait)
