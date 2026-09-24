"""Output formatting helpers for kimi-td-memory tools (v3 data plane shapes)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote
from typing import Any


def _truncate(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…(truncated)"


def _resolve_scene_path(path: str, data_dir: str, team_id: str, agent_id: str) -> str:
    """Resolve a v3 scenario path to an absolute local file when it exists.

    Scenario paths from the API are relative to the identity's profile dir
    (``<data_dir>/profiles/team%3A<team>%7Cagent%3A<agent>/``); scene blocks
    live one level deeper under ``scene_blocks/``.
    """
    if not data_dir:
        return path
    scope = quote(f"team:{team_id}|agent:{agent_id}", safe="")
    profile_root = Path(data_dir) / "profiles" / scope
    for candidate in (profile_root / path, profile_root / "scene_blocks" / path):
        if candidate.exists():
            return str(candidate)
    return path


def format_recall_result(
    core: dict[str, Any],
    scenarios: dict[str, Any],
    memories: dict[str, Any],
    data_dir: str = "",
    team_id: str = "default",
    agent_id: str = "default",
) -> str:
    """Assemble the client-side recall: L3 persona + L2 scene navigation + L1 hints."""
    sections: list[str] = []

    persona = (core or {}).get("content")
    if isinstance(persona, str) and persona.strip():
        # persona.md may have a Scene Navigation section appended (official
        # core/write strips it on write, older writers did not) — it is
        # redundant with the navigation section below, so cut it here.
        for marker in ("## 🗺️ Scene Navigation", "## Scene Navigation"):
            idx = persona.find(marker)
            if idx > 0:
                persona = persona[:idx]
                break
        # The stored persona may itself be wrapped in a markdown code fence;
        # unwrap it so we don't emit doubled fences below.
        lines = persona.strip().splitlines()
        if lines and re.match(r"^`{3,4}\s*markdown\s*$", lines[0]):
            lines = lines[1:]
        while lines and (re.match(r"^`{3,4}\s*$", lines[-1]) or lines[-1].strip() == "---"):
            lines.pop()
        persona = "\n".join(lines).strip()
        sections.append(f"<user-persona>\n````markdown\n{persona}\n````\n</user-persona>")

    entries = (scenarios or {}).get("entries") or []
    files = [e for e in entries if isinstance(e, dict) and not str(e.get("path", "")).endswith("/")]
    if files:
        lines = [
            "<scene-navigation>",
            "---",
            "## 🗺️ Scene Navigation (Scene Index)",
            "*以下是当前场景记忆的索引；Path 为本地 Markdown 文件时可直接用 Read 读取完整内容。*",
            "",
        ]
        for e in files:
            lines.append(f"### Path: {_resolve_scene_path(str(e.get('path')), data_dir, team_id, agent_id)}")
            if e.get("heat") is not None:
                lines.append(f"**热度**: {e['heat']}")
            updated = e.get("updated_at") or "-"
            lines.append(f"**更新**: {updated}")
            summary = e.get("summary")
            if summary:
                lines.append(f"Summary: {_truncate(str(summary), 300)}")
            lines.append("")
        lines.append("</scene-navigation>")
        sections.append("\n".join(lines))

    items = (memories or {}).get("items") or []
    if items:
        lines = ["<memory-hints>", "## 匹配的 L1 记忆", ""]
        for m in items:
            mtype = m.get("type", "memory")
            content = _truncate(str(m.get("content", "")), 500)
            scene = m.get("scene_name")
            prefix = f"- **[{mtype}]**"
            if scene:
                prefix += f" [scene: {scene}]"
            lines.append(f"{prefix} {content}")
            lines.append("")
        lines.append("</memory-hints>")
        sections.append("\n".join(lines))

    if not sections:
        return "No memories found yet for this identity."
    return "\n\n".join(sections)


def format_atomic_results(result: dict[str, Any]) -> str:
    """Format L1 atomic search results into a readable string."""
    items = (result or {}).get("items")
    if not isinstance(items, list):
        return json.dumps(result, ensure_ascii=False, indent=2)
    if not items:
        return "No matching memories found."
    lines = []
    for m in items:
        mtype = m.get("type", "memory")
        content = _truncate(str(m.get("content", "")), 500)
        lines.append(f"- [{mtype}] {content}")
    return "\n".join(lines)


def format_conversation_results(result: dict[str, Any]) -> str:
    """Format L0 conversation search results into a readable string."""
    messages = (result or {}).get("messages")
    if not isinstance(messages, list):
        return json.dumps(result, ensure_ascii=False, indent=2)
    if not messages:
        return "No matching conversations found."
    lines = []
    for m in messages:
        role = m.get("role", "?")
        session_id = m.get("session_id", "")
        content = _truncate(str(m.get("content", "")), 300)
        lines.append(f"- [{role}] ({session_id}) {content}")
    return "\n".join(lines)


def format_skill_results(result: dict[str, Any]) -> str:
    """Format skill search results into a readable string."""
    items = (result or {}).get("items")
    if not isinstance(items, list):
        return json.dumps(result, ensure_ascii=False, indent=2)
    if not items:
        return "No matching skills found."
    lines = []
    for s in items:
        line = f"- **{s.get('name', '?')}** (v{s.get('version', '?')})"
        desc = s.get("description") or s.get("snippet")
        if desc:
            line += f": {_truncate(str(desc), 200)}"
        lines.append(line)
    return "\n".join(lines)


def format_skill_detail(result: dict[str, Any]) -> str:
    """Format a full skill (with content) into a readable string."""
    name = result.get("name", "?")
    version = result.get("version", "?")
    status = result.get("status", "?")
    content = result.get("content") or "(no content)"
    return f"# Skill: {name} (v{version}, {status})\n\n{content}"
