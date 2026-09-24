#!/usr/bin/env python3
"""MCP stdio server for kimi-td-memory.

Exposes the td-memory tools over the MCP protocol (stdio transport) so the
Node.js Kimi Code CLI can call them. Talks to a MemoryCore v2.0.0 Gateway
over the v3 data plane (/v3/conversation, /v3/atomic, /v3/scenario, /v3/core).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from mcp.server.fastmcp import FastMCP

from client import (
    atomic_search,
    conversation_add,
    conversation_search,
    core_read,
    health,
    scenario_ls,
    skill_get_by_name,
    skill_search,
)
from config import data_dir, gateway_url, identity_fields, skill_identity_fields
from formatting import (
    format_atomic_results,
    format_conversation_results,
    format_recall_result,
    format_skill_detail,
    format_skill_results,
)
from session import resolve_session_key
from watcher_ctl import ensure_watcher, is_watcher_running, start_watcher, stop_watcher

mcp = FastMCP("td-memory")


@mcp.tool()
def td_recall(query: str, session_key: str | None = None) -> str:
    """Recall top-layer memory context from td-memory: L3 user persona, L2 scene navigation, and matching L1 memory hints. Use this first for user preferences, long-term goals, and macro project context; then drill down with td_search_memories (L1) or td_search_conversations (L0) when details are missing.

    Args:
        query: Recall query — natural language or keywords (required).
        session_key: Optional td-memory session key. If omitted, derived from current project directory.
    """
    ensure_watcher()
    identity = identity_fields()
    core = core_read()
    scenarios = scenario_ls()
    memories = atomic_search(query, limit=5)
    return format_recall_result(
        core,
        scenarios,
        memories,
        data_dir=data_dir(),
        team_id=identity.get("team_id", "default"),
        agent_id=identity.get("agent_id", "default"),
    )


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
    result = atomic_search(query, limit)
    return format_atomic_results(result)


@mcp.tool()
def td_search_conversations(query: str, limit: int = 5, session_key: str | None = None) -> str:
    """Search L0 raw conversations in td-memory. Use this to find exact past dialogues or when L1 memories are insufficient.

    Args:
        query: Search query — natural language or keywords.
        limit: Maximum results (default: 5, max: 20).
        session_key: Optional td-memory session key; restricts the search to that session. If omitted, derived from current project directory.
    """
    ensure_watcher()
    limit = max(1, min(int(limit), 20))
    key = session_key or resolve_session_key()
    result = conversation_search(query, limit, session_id=key)
    return format_conversation_results(result)


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
    return conversation_add(key, user_content, assistant_content)


@mcp.tool()
def td_end_session(session_key: str | None = None) -> str:
    """Note: with MemoryCore v2.0.0 the server-side pipeline extracts L1/L2/L3 automatically (on capture thresholds and idle timers), so there is nothing to flush manually. This tool is kept for workflow compatibility and simply confirms the session.

    Args:
        session_key: Optional td-memory session key. If omitted, derived from current project directory.
    """
    ensure_watcher()
    key = session_key or resolve_session_key()
    return (
        f"Session '{key}' noted. MemoryCore v2 extracts L1/L2/L3 automatically "
        "after captures and on idle timeouts — no manual flush is needed."
    )


@mcp.tool()
def td_search_skills(query: str, limit: int = 5) -> str:
    """Search skills in td-memory: reusable SOPs the server distilled from past work sessions (trigger boundaries, execution steps, verification rules). Use this before tackling a task type you may have solved before; fetch the full SOP with td_get_skill.

    Args:
        query: Search query — natural language or keywords.
        limit: Maximum results (default: 5, max: 20).
    """
    ensure_watcher()
    if not skill_identity_fields().get("team_id"):
        return (
            "Skill identity is not provisioned yet. Ask the user to run "
            "`python scripts/bootstrap_skill.py` in the plugin directory first "
            "(skill creation requires a metadata team/agent; chat memory is unaffected)."
        )
    limit = max(1, min(int(limit), 20))
    try:
        result = skill_search(query, limit)
    except RuntimeError as e:
        return f"Skill search unavailable: {e}"
    return format_skill_results(result)


@mcp.tool()
def td_get_skill(name: str) -> str:
    """Get the full content (SOP steps, verification rules) of a skill by its name, as listed by td_search_skills.

    Args:
        name: Skill name (required).
    """
    ensure_watcher()
    if not skill_identity_fields().get("team_id"):
        return (
            "Skill identity is not provisioned yet. Ask the user to run "
            "`python scripts/bootstrap_skill.py` in the plugin directory first."
        )
    try:
        result = skill_get_by_name(name)
    except RuntimeError as e:
        return f"Skill '{name}' not found: {e}"
    return format_skill_detail(result)


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
