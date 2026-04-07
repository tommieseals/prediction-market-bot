# Voice Interface Optimization Plan
**Created:** 2026-03-31
**Owner:** 💰💰Bottom Bitch💰💰

## Phase 1: ElevenLabs Voice Responses ✅ (Implement Now)

### Current State
- `sag` tool available (ElevenLabs TTS)
- TOOLS.md mentions: "Use voice for stories, movie summaries, storytime moments"
- No automatic voice response integration

### Implementation
1. Create `voice_responder.py` - Wrapper for `sag` tool
2. Add automatic voice response trigger
3. Test with sample conversation

### Testing
- Send test message → verify voice response generated
- Check audio quality/latency
- Verify file delivery via Telegram

---

## Phase 2: Telegram Transcript Forwarding ✅ (Implement Now)

### Current State
- Telegram bot configured (token: 7897…YRQA)
- User: @Dlowbands (ID: 939543801)
- No automatic transcript forwarding

### Implementation
1. Create `transcript_forwarder.py` - Monitor conversation logs
2. Parse webchat/voice transcripts
3. Auto-send to Rusty via Telegram message tool
4. Add to heartbeat for periodic sync

### Format
```
📝 TRANSCRIPT - [timestamp]
User: [transcription]
BB: [response summary]
---
```

---

## Phase 3: Context Loading Optimization ✅ (Implement Now)

### Current Problem
- Loading full AGENTS.md, SOUL.md, TOOLS.md every turn
- High token burn on repeated context
- Slow response times

### Solution
1. Create `context_cache.json` - Session-based cache
2. Load full context once per session
3. Refresh only on heartbeat or manual trigger
4. Use lightweight context summaries for normal turns

### Expected Savings
- Current: ~25k tokens/turn (estimated)
- Optimized: ~5k tokens/turn
- **80% token reduction**

---

## Phase 4: Streaming Architecture (Future - Design Only)

### Current Flow
```
User speaks → Full transcription → Process → Respond
```

### Future Flow
```
User speaks → Streaming transcription → Parallel processing → Streaming response
```

### Requirements
- WebSocket connection for real-time data
- Streaming API support (Whisper API, Claude streaming)
- Client-side buffering
- Interrupt handling (stop mid-response)

### NOT implementing now (architecture change required)
- Requires changes to Clawdbot core
- Needs WebSocket infrastructure
- Document for future reference only

---

## Implementation Order
1. ✅ Voice responses (quick win, high impact)
2. ✅ Telegram forwarding (automation, tracking)
3. ✅ Context optimization (cost savings)
4. 📋 Streaming (design doc only, implement later)

---

## Success Metrics
- Voice response latency: <5 seconds
- Transcript delivery: 100% of conversations
- Token savings: 80% reduction
- User satisfaction: Seamless experience
