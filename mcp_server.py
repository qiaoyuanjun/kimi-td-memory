#!/usr/bin/env python3
"""MCP stdio server for kimi-td-memory.

Exposes the td-memory tools over the MCP protocol (stdio transport) so the
Node.js Kimi Code CLI can call them. Tool logic reuses the same modules the
old command-style tools used; only the transport changed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from mcp.server.fastmcp import FastMCP

from client import capture, end_session, health, recall, search_conversations, search_memories
from config import gateway_url
from formatting import format_recall_result, format_search_results
from session import resolve_session_key
from watcher_ctl import ensure_watcher, is_watcher_running, start_watcher, stop_watcher

mcp = FastMCP("td-memory")


@mcp.tool()
def td_recall(query: str, session_key: str | None = None) -> str:
    """Recall top-layer memory context from td-memory: L3 user persona, L2 scene navigation, and matching L1 memory hints. Use this first for user preferences, long-term goals, and macro project context; then drill down with td_search_memories (L1) or td_search_conversations (L0) when details are missing. Scene block paths in the scene navigation can be read directly as Markdown files.

    Args:
        query: Recall query — natural language or keywords (required).
        session_key: Optional td-memory session key. If omitted, derived from current project directory.
    """
    ensure_watcher()
    key = session_key or resolve_session_key()
    result = recall(key, query)
    return format_recall_result(result)


@mcp.tool()
def td_search_memories(query: str, limit: int = 5, session_key: str | None = None) -> str:
    """Search L1 atomic memories in td-memory. Use this to recall distilled facts, decisions, and project context from past sessions.

    Args:
        query: Search query — natural language or keywords.
        limit: Maximum results (default: 5, max: 20).
        session_key: Optional td-memory session key. If omitted, derived from current project directory.
    """
    ensure_watcher()
    limit = max(1, min(int(limit), 20))
    key = session_key or resolve_session_key()
    result = search_memories(key, query, limit)
    return format_search_results(result)


@mcp.tool()
def td_search_conversations(query: str, limit: int = 5, session_key: str | None = None) -> str:
    """Search L0 raw conversations in td-memory. Use this to find exact past dialogues or when L1 memories are insufficient.

    Args:
        query: Search query — natural language or keywords.
        limit: Maximum results (default: 5, max: 20).
        session_key: Optional td-memory session key. If omitted, derived from current project directory.
    """
    ensure_watcher()
    limit = max(1, min(int(limit), 20))
    key = session_key or resolve_session_key()
    result = search_conversations(key, query, limit)
    return format_search_results(result)


@mcp.tool()
def td_capture(user_content: str, assistant_content: str, session_key: str | None = None) -> dict:
    """Manually capture a user/assistant turn into td-memory. Usually not needed because the watcher captures automatically.

    Args:
        user_content: User message text.
        assistant_content: Assistant message text.
        session_key: Optional td-memory session key. If omitted, derived from current project directory.
    """
    ensure_watcher()
    if not user_content or not assistant_content:
        raise ValueError("user_content and assistant_content are required")
    key = session_key or resolve_session_key()
    return capture(key, user_content, assistant_content)


@mcp.tool()
def td_end_session(session_key: str | None = None) -> dict:
    """Flush the current session and trigger L1/L2/L3 extraction immediately. Use at the end of a significant discussion or before switching topics.

    Args:
        session_key: Optional td-memory session key. If omitted, derived from current project directory.
    """
    ensure_watcher()
    key = session_key or resolve_session_key()
    return end_session(key)


@mcp.tool()
def td_health() -> dict:
    """Check whether the TDAI Gateway is reachable and ensure the watcher is running."""
    result = health()
    # Avoid a redundant /health call by checking directly and starting with
    # skip_health_check=True.
    if is_watcher_running():
        result["watcher"] = {"running": True, "started": False}
    else:
        result["watcher"] = start_watcher(skip_health_check=True)
    return result


@mcp.tool()
def td_status() -> dict:
    """Show kimi-td-memory status: gateway URL and watcher process state. Starts the watcher if it is not running."""
    watcher_status = ensure_watcher()
    return {
        "gateway_url": gateway_url(),
        "watcher_running": is_watcher_running(),
        "watcher_status": watcher_status,
    }


@mcp.tool()
def td_stop_watcher() -> dict:
    """Stop the kimi-td-memory auto-capture watcher."""
    return stop_watcher()


if __name__ == "__main__":
    mcp.run()
