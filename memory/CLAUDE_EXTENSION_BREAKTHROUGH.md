# CLAUDE EXTENSION CONTROL - THE HOLY GRAIL

**Date:** 2026-03-16 11:01 PM CST
**Status:** FULLY OPERATIONAL

---

## The Achievement

I can now send messages to the Claude Chrome extension from Telegram and get responses.
Claude can SEE and INTERACT with ANY webpage Rusty has open.

**This is AI-to-AI communication at the desktop level.**

---

## The Pipeline

```
Telegram → Clawdbot → run_claude.py → Chrome Claude Extension → Response → Screenshot
```

---

## The Key Breakthrough

**Single Python process prevents focus stealing.**

PowerShell between commands = broken (focus gets stolen)
All steps in ONE Python script = working

---

## The Magic Coordinates (1920x1080 screen)

```python
SIDEBAR_INPUT_X = 1725
SIDEBAR_INPUT_Y = 912
```

These are the exact coordinates of the Claude extension's input field.

---

## Usage

```bash
python C:/Users/User/clawd/run_claude.py "What page am I on?"
```

---

## The Working Script Pattern

```python
# All in ONE process - this is critical!

1. find_and_activate_chrome()
   - Use ctypes.windll.user32.SetForegroundWindow()
   - Prefer Chrome windows with "claude" in title

2. pyautogui.click(1725, 912)
   - Click the sidebar input

3. pyautogui.hotkey('ctrl', 'a')
   - Clear any existing text

4. pyautogui.typewrite(message, interval=0.03)
   - Type the message character by character
   - NOT clipboard (clipboard can fail)

5. pyautogui.press('enter')
   - Send the message

6. time.sleep(6)
   - Wait for Claude to respond

7. screenshot.crop((1480, 0, 1920, 1080))
   - Capture just the sidebar area
   - Resize for readability
```

---

## Files

- `C:\Users\User\clawd\claude_sidebar_send.py` - Main script with all logic
- `C:\Users\User\clawd\run_claude.py` - Wrapper for easy calling

---

## What This Unlocks

- **Summarize any webpage** - "What's on this page?"
- **Extract data** - "Get all the prices from this table"
- **Fill forms** - "Fill out this application with my info"
- **Navigate** - "Click the Sign In button"
- **Chain commands** - Claude sees results and continues
- **Any AI task on any webpage** - The possibilities are endless

---

## Why This Is Huge

Other bots are limited to APIs and structured data.

I can now use ANY tool that has a UI:
- Claude extension (page analysis, summarization, actions)
- ChatGPT
- Any Chrome extension
- Any desktop application

**This is full desktop-level AI integration.**

---

## Rusty's Vision Realized

> "Give the bot the ability to see and use every tool like a regular user would be able to do."

**DONE.**
