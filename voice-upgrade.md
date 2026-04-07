# Voice Interface Upgrade - Implementation Log

## Current Status (2026-04-01)

### ✅ What's Already Working
- Webchat interface with voice input (browser speech-to-text)
- Clawdbot gateway running (ws://127.0.0.1:18789)
- Telegram bot configured (7897105421)
- Built-in TTS tool available (Edge TTS = FREE)

### 🔧 What Needs Implementation

#### 1. Voice Responses (TTS)
**Tool:** `tts` (built-in Clawdbot tool)
**Provider:** Edge TTS (Microsoft neural voices - FREE, no API key needed!)
**Status:** ⏳ Ready to enable

#### 2. Context Optimization
**Problem:** Full AGENTS.md, SOUL.md, TOOLS.md loaded every turn
**Solution:** Lazy-load on demand, cache in session
**Status:** ⏳ Config change needed

#### 3. Telegram Forwarding
**Target:** @Dlowbands (939543801)
**Format:** Transcript chunks with timestamps
**Status:** ⏳ Needs implementation

#### 4. Streaming Feel
**Current:** Chunk-by-chunk transcription
**Better:** Accumulated context + faster responses
**Status:** ⏳ Workflow optimization

---

## Implementation Steps

### STEP 1: Enable Voice Responses ✅ IN PROGRESS

**Method:** Use built-in `tts` tool with Edge TTS

**Test command:**
```bash
# Via Clawdbot tool (will test next)
```

**Expected output:** MEDIA:/path/to/audio.mp3

**Edge TTS Voices Available:**
- en-US-JennyNeural (female, professional)
- en-US-GuyNeural (male, professional) 
- en-US-AriaNeural (female, cheerful)
- en-US-DavisNeural (male, calm)
- en-US-AmberNeural (female, warm)

**Recommended:** en-US-GuyNeural (professional male voice for Bottom Bitch 💰)

---

### STEP 2: Configure TTS in Clawdbot

**Config file:** `C:\Users\User\.clawdbot\clawdbot.json`

**Add to config:**
```json
{
  "messages": {
    "tts": {
      "enabled": true,
      "auto": "always",
      "provider": "edge",
      "edge": {
        "voice": "en-US-GuyNeural",
        "lang": "en-US",
        "rate": "+5%",
        "enabled": true
      }
    }
  }
}
```

**Why Edge TTS:**
- ✅ FREE (no API key needed)
- ✅ High quality neural voices
- ✅ No rate limits
- ✅ Built into Clawdbot

---

### STEP 3: Context Optimization

**Current load per turn:** ~25KB+ (AGENTS.md + SOUL.md + TOOLS.md + IDENTITY.md + USER.md + HEARTBEAT.md)

**Optimization strategy:**
1. Load SOUL.md + IDENTITY.md once per session (personality/role)
2. AGENTS.md = reference only (don't load every turn)
3. TOOLS.md = on-demand (only when specific tool needed)
4. HEARTBEAT.md = heartbeat polls only
5. USER.md = cached (doesn't change)

**Implementation:** Clawdbot workspace config (check compaction settings)

---

### STEP 4: Telegram Transcript Forwarding

**Target:** Direct message to @Dlowbands (939543801)
**Format:**
```
🎤 Voice Transcript - HH:MM:SS

User: [transcribed text]

💰: [my response]

---
```

**Implementation:** Custom hook in Clawdbot or external script

**Method A (Simple - 5 min):**
```powershell
# PowerShell script that watches session logs and forwards
```

**Method B (Integrated - 30 min):**
```javascript
// Clawdbot internal hook that fires on each message
```

---

### STEP 5: Workflow Optimization

**Current flow:**
1. User speaks → browser STT → text chunk
2. "transcribe and respond to 'X'" message sent
3. Full context loaded
4. Response generated
5. Text displayed

**Optimized flow:**
1. User speaks → browser STT → text chunk  
2. Clawdbot receives, maintains session context
3. TTS enabled → response includes voice
4. Transcript auto-forwarded to Telegram
5. Voice plays in browser

**Key improvements:**
- Session context persistence (reduce reloading)
- Voice output (engaging)
- Telegram backup (tracking)
- Faster turnaround

---

## Testing Checklist

- [ ] TTS tool works (test with simple text)
- [ ] Edge TTS configured with good voice
- [ ] Voice plays in webchat interface
- [ ] Telegram forwarding working
- [ ] Context optimization reduces load time
- [ ] End-to-end test: speak → hear response

---

## Next Actions

1. ✅ Test TTS tool now
2. ⏳ Update Clawdbot config with TTS settings
3. ⏳ Implement Telegram forwarding script
4. ⏳ Optimize context loading
5. ⏳ End-to-end test

