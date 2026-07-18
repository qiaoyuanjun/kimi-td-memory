"""Shared helpers for kimi-td-memory plugin and watcher.

This module re-exports functions from the split submodules for backward
compatibility. New code should import directly from the specific modules.
"""

from __future__ import annotations

from client import capture, end_session, health, search_conversations, search_memories, tdai_call
from config import gateway_api_key, gateway_url, get_config, get_watcher_pid_file, get_watcher_state_dir
from formatting import format_search_results
from session import find_project_root, resolve_session_key
from text import extract_text, is_system_noise, strip_system_reminders
from watcher_ctl import ensure_watcher, is_watcher_running, start_watcher, stop_watcher

__all__ = [
    "capture",
    "end_session",
    "ensure_watcher",
    "extract_text",
    "find_project_root",
    "format_search_results",
    "gateway_api_key",
    "gateway_url",
    "get_config",
    "get_watcher_pid_file",
    "get_watcher_state_dir",
    "health",
    "is_system_noise",
    "is_watcher_running",
    "resolve_session_key",
    "search_conversations",
    "search_memories",
    "start_watcher",
    "stop_watcher",
    "strip_system_reminders",
    "tdai_call",
]
