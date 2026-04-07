# Voice Optimization - Quick Reference

## 🎯 Quick Commands

### Context Optimization (Use Every Turn)
```bash
# Get lightweight context (ALWAYS use this instead of loading full files)
python context_optimizer.py --get voice_session

# Refresh cache (only when files change)
python context_optimizer.py --refresh voice_session
```

### Voice Response Generation
```bash
# Generate voice response
python voice_responder.py "Your response text here"
```

### Transcript Forwarding
```powershell
# Send transcript to Telegram
.\send_transcript.ps1 "User input" "Bot response"
```

---

## 💰 Token Savings

**Before Optimization:**
```
Turn 1: Load AGENTS.md (10k) + SOUL.md (5k) + TOOLS.md (8k) = 23k tokens
Turn 2: Load AGENTS.md (10k) + SOUL.md (5k) + TOOLS.md (8k) = 23k tokens
Turn 3: Load AGENTS.md (10k) + SOUL.md (5k) + TOOLS.md (8k) = 23k tokens
Total: 69k tokens for 3 turns
```

**After Optimization:**
```
Turn 1: Load full context = 23k tokens (cache init)
Turn 2: Lightweight summary = 0.5k tokens
Turn 3: Lightweight summary = 0.5k tokens
Total: 24k tokens for 3 turns (65% savings!)
```

---

## 🔧 Integration Pattern

```python
# Example voice conversation handler
def handle_voice_conversation(user_transcription):
    session_id = "voice_main"
    
    # 1. Get optimized context (instead of loading full files)
    context = get_lightweight_context(session_id)
    
    # 2. Generate response with AI
    bot_response_text = ai_generate(user_transcription, context)
    
    # 3. Create voice response
    audio_file = generate_voice(bot_response_text)
    
    # 4. Log to Telegram
    send_transcript(user_transcription, bot_response_text)
    
    return audio_file
```

---

## 📊 Cache Stats

```bash
python context_optimizer.py --stats
```

Output:
```json
{
  "total_sessions_cached": 1,
  "cache_directory": "C:\\Users\\USER\\clawd\\memory\\context_cache",
  "context_files_tracked": 6
}
```

---

## 🎬 Test Commands

### Test Telegram Forwarding
```powershell
.\send_transcript.ps1 "Test user input" "Test bot response"
```

### Test Context Cache
```bash
# Init
python context_optimizer.py --init test_session

# Get
python context_optimizer.py --get test_session
```

### Test Voice Generation
```bash
python voice_responder.py "This is a test voice response"
```

---

## 📁 File Locations

- Context cache: `C:\Users\USER\clawd\memory\context_cache\`
- Voice scripts: `C:\Users\USER\clawd\voice_responder.py`
- Transcript scripts: `C:\Users\USER\clawd\send_transcript.ps1`
- Optimizer: `C:\Users\USER\clawd\context_optimizer.py`
- Full docs: `C:\Users\USER\clawd\VOICE_OPTIMIZATION_README.md`

---

💰 **Remember:** Use lightweight context on EVERY turn. Only refresh when files actually change!
