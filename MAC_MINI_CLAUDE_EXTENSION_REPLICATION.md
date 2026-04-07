# Claude Extension Control - Mac Mini Replication Guide

**Created:** 2026-03-16
**Source:** Dell Windows machine (100.119.87.108)
**Target:** Mac Mini (100.88.105.106)

---

## Overview

This guide explains how to replicate the Claude Chrome extension control capability on Mac Mini.

**What it does:** Send messages to the Claude Chrome extension from Telegram and get responses. Claude can see and interact with any webpage.

---

## Prerequisites

### 1. Install Python Dependencies

```bash
pip3 install pyautogui pillow pyobjc-framework-Quartz pyobjc-core
```

### 2. Install Chrome with Claude Extension

- Install Google Chrome
- Add the Claude extension from Chrome Web Store
- Sign in to Claude

### 3. Grant Accessibility Permissions

System Settings > Privacy & Security > Accessibility
- Add Terminal
- Add Python

---

## The Key Script Pattern

**CRITICAL:** Everything must run in ONE Python process.
Separate shell commands will lose focus between steps.

```python
import pyautogui
import time
import subprocess

# Disable failsafe for automation
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

# IMPORTANT: Adjust these for your screen resolution!
# These are for 1920x1080 - will be different on Mac
SIDEBAR_INPUT_X = 1725  # Adjust for Mac screen
SIDEBAR_INPUT_Y = 912   # Adjust for Mac screen

def find_and_activate_chrome():
    # Mac version - use AppleScript to activate Chrome
    script = '''
    tell application "Google Chrome"
        activate
    end tell
    '''
    subprocess.run(['osascript', '-e', script])
    time.sleep(0.6)

def send_to_claude_sidebar(message):
    # Step 1: Activate Chrome
    find_and_activate_chrome()
    
    # Step 2: Click the sidebar input
    # NOTE: You must find the correct coordinates for Mac!
    pyautogui.click(SIDEBAR_INPUT_X, SIDEBAR_INPUT_Y)
    time.sleep(0.3)
    
    # Step 3: Clear any existing text
    pyautogui.hotkey('command', 'a')  # Mac uses command, not ctrl
    time.sleep(0.1)
    
    # Step 4: Type the message
    pyautogui.typewrite(message, interval=0.03)
    time.sleep(0.2)
    
    # Step 5: Send
    pyautogui.press('enter')
    
    # Step 6: Wait for response
    time.sleep(6)
    
    # Step 7: Screenshot
    screenshot = pyautogui.screenshot()
    screenshot.save('claude-response.png')

if __name__ == "__main__":
    import sys
    msg = sys.argv[1] if len(sys.argv) > 1 else "Hello! What page am I on?"
    send_to_claude_sidebar(msg)
```

---

## Finding the Correct Coordinates

The sidebar input coordinates depend on:
- Screen resolution
- Chrome window size and position
- Claude extension sidebar width

### To Find Your Coordinates:

```python
import pyautogui
import time

# Run this, then quickly position mouse over the Claude sidebar input
time.sleep(3)
print(pyautogui.position())
```

Or use screenshot analysis:
```python
import pyautogui
screenshot = pyautogui.screenshot()
screenshot.save('screen.png')
# Open screen.png and measure the sidebar input position
```

---

## Mac-Specific Differences

| Windows | Mac |
|---------|-----|
| `ctrl` | `command` |
| `ctypes.windll.user32.SetForegroundWindow` | AppleScript `tell application "Chrome" activate` |
| `pygetwindow` | Not needed (use AppleScript) |

---

## Testing

1. Open Chrome with Claude extension visible
2. Navigate to any webpage
3. Run the script:

```bash
python3 claude_sidebar_send.py "What page am I on?"
```

4. Check claude-response.png for the screenshot

---

## Troubleshooting

### Clicks Not Landing
- Check coordinates match your screen resolution
- Make sure Chrome is not minimized
- Grant accessibility permissions

### Focus Stolen
- Make sure ALL steps are in ONE Python script
- Don't use shell commands between pyautogui calls

### Extension Not Visible
- Click the Claude extension icon in toolbar first
- Make sure sidebar is pinned/open

---

## Integration with Clawdbot

Once the script works locally, integrate with Clawdbot:

1. Create the script at `~/clawd/claude_sidebar_send.py`
2. Call it via computer-use skill or direct exec
3. Read the response screenshot

---

## The Breakthrough

The key insight: **Single Python process**.

When you run separate commands, the OS can shift focus between them.
By keeping everything in one script, focus stays on Chrome and clicks land correctly.

This is what makes the full pipeline work:
```
Telegram → Clawdbot → python script → Chrome Claude Extension → Response
```
