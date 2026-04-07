#!/usr/bin/env python3
"""
Context Loading Optimizer
Reduces token burn by caching session context and loading incrementally.

Usage:
    python context_optimizer.py --init session_id  # Initialize cache
    python context_optimizer.py --get session_id   # Get lightweight context
    python context_optimizer.py --refresh session_id  # Force full refresh
    python context_optimizer.py --stats  # Show cache statistics
"""

import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path

CACHE_DIR = Path("C:/Users/USER/clawd/memory/context_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Files to cache
CONTEXT_FILES = {
    "AGENTS.md": "C:/Users/USER/clawd/AGENTS.md",
    "SOUL.md": "C:/Users/USER/clawd/SOUL.md",
    "TOOLS.md": "C:/Users/USER/clawd/TOOLS.md",
    "USER.md": "C:/Users/USER/clawd/USER.md",
    "IDENTITY.md": "C:/Users/USER/clawd/IDENTITY.md",
    "HEARTBEAT.md": "C:/Users/USER/clawd/HEARTBEAT.md"
}

def get_file_hash(filepath):
    """Get MD5 hash of file content."""
    try:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except FileNotFoundError:
        return None

def get_lightweight_summary():
    """
    Generate lightweight context summary (instead of full files).
    This is what should be loaded on MOST turns.
    """
    summary = {
        "identity": {
            "name": "💰💰Bottom Bitch💰💰",
            "role": "Infrastructure Operations Lead",
            "emoji": "💰",
            "mission": "PREVENT OUTAGES. STRENGTHEN THE SYSTEM. BE PROACTIVE."
        },
        "user": {
            "name": "Tommie Seals (Rusty)",
            "telegram": "@Dlowbands (939543801)",
            "timezone": "America/Chicago (currently in Europe/Berlin)"
        },
        "key_nodes": {
            "rtx": "100.115.12.91 (GPU primary)",
            "mac_mini": "100.88.105.106 (orchestrator)",
            "mac_pro": "100.67.192.21 (compute)",
            "dell": "100.119.87.108 (failsafe)"
        },
        "core_rules": [
            "Monitor all nodes every heartbeat",
            "Fix issues before outages",
            "Alert on security threats",
            "Optimize performance constantly",
            "Use RTX GPU for heavy models"
        ]
    }
    return summary

def init_cache(session_id):
    """
    Initialize context cache for a session.
    Loads and caches all context files.
    """
    cache_file = CACHE_DIR / f"{session_id}.json"
    
    cache_data = {
        "session_id": session_id,
        "created": datetime.now().isoformat(),
        "last_refresh": datetime.now().isoformat(),
        "file_hashes": {},
        "lightweight_summary": get_lightweight_summary()
    }
    
    # Hash all context files
    for name, filepath in CONTEXT_FILES.items():
        file_hash = get_file_hash(filepath)
        cache_data["file_hashes"][name] = file_hash
    
    # Save cache
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)
    
    print(json.dumps({
        "success": True,
        "session_id": session_id,
        "cached_files": len(cache_data["file_hashes"]),
        "cache_file": str(cache_file)
    }))
    
    return cache_data

def get_context(session_id, force_refresh=False):
    """
    Get context for a session.
    Returns lightweight summary if cache is valid,
    or triggers full reload if files changed.
    """
    cache_file = CACHE_DIR / f"{session_id}.json"
    
    if not cache_file.exists() or force_refresh:
        return init_cache(session_id)
    
    # Load existing cache
    with open(cache_file, 'r') as f:
        cache_data = json.load(f)
    
    # Check if any files changed
    files_changed = []
    for name, filepath in CONTEXT_FILES.items():
        current_hash = get_file_hash(filepath)
        cached_hash = cache_data["file_hashes"].get(name)
        
        if current_hash != cached_hash:
            files_changed.append(name)
    
    if files_changed:
        # Files changed - refresh cache
        print(json.dumps({
            "info": "Context files changed, refreshing cache",
            "changed_files": files_changed
        }))
        return init_cache(session_id)
    
    # Cache valid - return lightweight summary
    print(json.dumps({
        "success": True,
        "cache_valid": True,
        "using_lightweight_summary": True,
        "session_id": session_id
    }))
    
    return cache_data["lightweight_summary"]

def show_stats():
    """Show cache statistics."""
    cache_files = list(CACHE_DIR.glob("*.json"))
    
    stats = {
        "total_sessions_cached": len(cache_files),
        "cache_directory": str(CACHE_DIR),
        "context_files_tracked": len(CONTEXT_FILES)
    }
    
    print(json.dumps(stats, indent=2))

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: python context_optimizer.py --init|--get|--refresh session_id OR --stats"
        }))
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "--stats":
        show_stats()
    
    elif command in ["--init", "--get", "--refresh"]:
        if len(sys.argv) < 3:
            print(json.dumps({"error": "Session ID required"}))
            sys.exit(1)
        
        session_id = sys.argv[2]
        
        if command == "--init":
            init_cache(session_id)
        elif command == "--get":
            result = get_context(session_id, force_refresh=False)
            print(json.dumps(result, indent=2))
        elif command == "--refresh":
            result = get_context(session_id, force_refresh=True)
            print(json.dumps(result, indent=2))
    
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)

if __name__ == "__main__":
    main()
