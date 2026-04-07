#!/usr/bin/env python3
"""
Memory Auto Search - Coordination layer for mem0-memory + recall-memory
Automatically searches both memory systems and injects relevant context before LLM responses.
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path


def run_mem0_search(query, agent_id, limit=10):
    """Search mem0-memory semantic store."""
    script_path = Path.home() / ".clawdbot" / "skills" / "mem0-memory" / "mem0_skill.py"
    
    if not script_path.exists():
        return []
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--agent-id", agent_id, "search", query, "--limit", str(limit)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print(f"WARNING: mem0 search failed: {result.stderr}", file=sys.stderr)
            return []
        
        # Parse the output - it's human-readable format, not JSON
        # Example: "  [0.28] (unknown) Risk controls cannot be overridden"
        memories = []
        for line in result.stdout.strip().split("\n")[1:]:  # Skip header line
            if line.strip() and line.startswith("  ["):
                # Extract the memory content after the metadata
                parts = line.split(") ", 1)
                if len(parts) == 2:
                    memories.append(parts[1].strip())
        
        return memories
    
    except Exception as e:
        print(f"WARNING: mem0 search error: {e}", file=sys.stderr)
        return []


def run_recall_search(query, agent_id, limit=10):
    """Search recall-memory conversation history."""
    script_path = Path.home() / ".clawdbot" / "skills" / "recall-memory" / "recall_skill.py"
    
    if not script_path.exists():
        return []
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--agent-id", agent_id, "search", query, "--limit", str(limit)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print(f"WARNING: recall search failed: {result.stderr}", file=sys.stderr)
            return []
        
        # Parse the output - similar format to mem0
        conversations = []
        for line in result.stdout.strip().split("\n")[1:]:  # Skip header line
            if line.strip() and not line.startswith("Total"):
                conversations.append(line.strip())
        
        return conversations
    
    except Exception as e:
        print(f"WARNING: recall search error: {e}", file=sys.stderr)
        return []


def estimate_tokens(text):
    """Rough token estimate (1 token ≈ 4 chars)."""
    return len(text) // 4


def main():
    parser = argparse.ArgumentParser(description="Auto-search both memory systems")
    parser.add_argument("--query", required=True, help="Search query (usually the user message)")
    parser.add_argument("--agent-id", default="bottom-bitch", help="Bot agent ID")
    parser.add_argument("--mem0-limit", type=int, default=10, help="Max mem0 results")
    parser.add_argument("--recall-limit", type=int, default=5, help="Max recall results")
    parser.add_argument("--max-tokens", type=int, default=2000, help="Max context tokens to inject")
    
    args = parser.parse_args()
    
    # Search both systems
    mem0_memories = run_mem0_search(args.query, args.agent_id, args.mem0_limit)
    recall_conversations = run_recall_search(args.query, args.agent_id, args.recall_limit)
    
    # Combine and truncate to max tokens
    combined_text = "\n".join(mem0_memories + recall_conversations)
    total_tokens = estimate_tokens(combined_text)
    
    if total_tokens > args.max_tokens:
        # Truncate recall first (mem0 facts are higher priority)
        while recall_conversations and total_tokens > args.max_tokens:
            recall_conversations.pop()
            combined_text = "\n".join(mem0_memories + recall_conversations)
            total_tokens = estimate_tokens(combined_text)
        
        # If still over, truncate mem0
        while mem0_memories and total_tokens > args.max_tokens:
            mem0_memories.pop()
            combined_text = "\n".join(mem0_memories + recall_conversations)
            total_tokens = estimate_tokens(combined_text)
    
    # Output as JSON
    output = {
        "mem0_memories": mem0_memories,
        "recall_conversations": recall_conversations,
        "total_context_tokens": total_tokens,
        "query": args.query
    }
    
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
