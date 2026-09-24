"""Shared helpers for kimi-td-memory plugin and watcher.

This module re-exports functions from the split submodules for backward
compatibility. New code should import directly from the specific modules.
"""

from __future__ import annotations

from client import (
    atomic_search,
    conversation_add,
    conversation_search,
    core_read,
    health,
    scenario_ls,
    skill_conversation_add,
    skill_get,
    skill_get_by_name,
    skill_list,
    skill_search,
    tdai_call,
)
from config import (
    gateway_api_key,
    gateway_url,
    get_config,
    get_watcher_pid_file,
    get_watcher_state_dir,
    identity_fields,
    service_id,
    skill_identity_fields,
)
from formatting import (
    format_atomic_results,
    format_conversation_results,
    format_recall_result,
    format_skill_detail,
    format_skill_results,
)
from session import find_project_root, resolve_session_key
from text import extract_text, is_system_noise, strip_system_reminders
from watcher_ctl import ensure_watcher, is_watcher_running, start_watcher, stop_watcher

__all__ = [
    "atomic_search",
    "conversation_add",
    "conversation_search",
    "core_read",
    "ensure_watcher",
    "extract_text",
    "find_project_root",
    "format_atomic_results",
    "format_conversation_results",
    "format_recall_result",
    "format_skill_detail",
    "format_skill_results",
    "gateway_api_key",
    "gateway_url",
    "get_config",
    "get_watcher_pid_file",
    "get_watcher_state_dir",
    "health",
    "identity_fields",
    "is_system_noise",
    "is_watcher_running",
    "resolve_session_key",
    "scenario_ls",
    "service_id",
    "skill_conversation_add",
    "skill_get",
    "skill_get_by_name",
    "skill_identity_fields",
    "skill_list",
    "skill_search",
    "start_watcher",
    "stop_watcher",
    "strip_system_reminders",
    "tdai_call",
]
