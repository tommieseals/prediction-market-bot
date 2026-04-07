#!/usr/bin/env python3
"""
Voice Response Generator
Uses ElevenLabs TTS via Clawdbot's 'sag' tool to generate voice responses.

Usage:
    python voice_responder.py "Your text here"
    python voice_responder.py --file response.txt
"""

import sys
import subprocess
import json
from pathlib import Path

def generate_voice_response(text, output_file=None):
    """
    Generate voice response using 'sag' (ElevenLabs TTS).
    
    Args:
        text: Text to convert to speech
        output_file: Optional output file path
    
    Returns:
        Path to generated audio file
    """
    if not text or text.strip() == "":
        print(json.dumps({"error": "No text provided"}))
        return None
    
    # Use Clawdbot's TTS tool
    # According to the tools, we have access to the 'tts' function
    # But we need to call it via subprocess or API
    
    # For now, let's use a direct approach
    try:
        # Call the tts tool (this would be through Clawdbot gateway)
        # Since we're in the Python script, we'll use requests to hit the gateway
        import requests
        
        gateway_url = "http://localhost:18789/v1/tts"
        
        response = requests.post(
            gateway_url,
            json={
                "text": text,
                "channel": "telegram"  # Format for Telegram delivery
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            media_path = result.get("media_path")
            print(json.dumps({
                "success": True,
                "audio_file": media_path,
                "text": text[:100]
            }))
            return media_path
        else:
            print(json.dumps({
                "error": f"TTS failed: {response.status_code}",
                "details": response.text
            }))
            return None
            
    except Exception as e:
        print(json.dumps({
            "error": f"Voice generation failed: {str(e)}"
        }))
        return None

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python voice_responder.py 'text' or --file path"}))
        sys.exit(1)
    
    if sys.argv[1] == "--file":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "File path required"}))
            sys.exit(1)
        with open(sys.argv[2], 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        text = ' '.join(sys.argv[1:])
    
    generate_voice_response(text)

if __name__ == "__main__":
    main()
