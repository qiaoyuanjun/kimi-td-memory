"""Shared helpers for kimi-td-memory plugin and watcher."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib import request, error


def get_config() -> dict[str, Any]:
    """Load plugin config.json."""
    plugin_dir = Path(__file__).parent.resolve()
    config_path = plugin_dir / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def gateway_url() -> str:
    """Return TDAI Gateway URL from env or config."""
    return os.environ.get("TDAI_GATEWAY_URL") or get_config().get("gateway_url", "http://127.0.0.1:8420")


def find_project_root(cwd: Path | None = None) -> Path:
    """Find project root by looking for .git or common markers."""
    start = cwd or Path.cwd()
    path = start.resolve()
    markers = [".git", ".kimi", "pom.xml", "package.json", "pyproject.toml"]
    for parent in [path, *path.parents]:
        for marker in markers:
            if (parent / marker).exists():
                return parent
    return path


def resolve_session_key(cwd: Path | None = None) -> str:
    """Resolve td-memory session_key for current Kimi workspace/project."""
    cfg = get_config()
    project_root = find_project_root(cwd)

    # Apply user-defined mappings first
    mappings = cfg.get("session_key_map", {})
    for pattern, session_key in mappings.items():
        if pattern in str(project_root):
            return session_key

    # Default: use project directory name + "-context"
    return f"{project_root.name}-context"


def tdai_call(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make an HTTP call to TDAI Gateway and return JSON response."""
    url = gateway_url().rstrip("/") + path
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"}
    if cfg := get_config():
        api_key = cfg.get("gateway_api_key") or ""
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            if body:
                return json.loads(body)
            return {}
    except error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"TDAI Gateway error {e.code}: {body}") from e


def capture(session_key: str, user_content: str, assistant_content: str) -> dict[str, Any]:
    """Capture a single user/assistant turn."""
    return tdai_call(
        "POST",
        "/capture",
        {
            "session_key": session_key,
            "user_content": user_content,
            "assistant_content": assistant_content,
        },
    )


def end_session(session_key: str) -> dict[str, Any]:
    return tdai_call("POST", "/session/end", {"session_key": session_key})


def search_memories(session_key: str, query: str, limit: int = 5) -> dict[str, Any]:
    return tdai_call(
        "POST",
        "/search/memories",
        {"session_id": session_key, "query": query, "limit": limit},
    )


def search_conversations(session_key: str, query: str, limit: int = 5) -> dict[str, Any]:
    return tdai_call(
        "POST",
        "/search/conversations",
        {"session_id": session_key, "query": query, "limit": limit},
    )


def health() -> dict[str, Any]:
    return tdai_call("GET", "/health")


def extract_text(content: Any) -> str:
    """Extract plain text from Kimi context.jsonl content field."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    parts.append(str(item["text"]))
                elif item.get("type") == "think":
                    # Skip internal reasoning by default
                    continue
        return "\n".join(parts)
    return str(content)


def is_system_noise(text: str) -> bool:
    """Filter out compaction output and system noise."""
    noise_markers = [
        "<system>Previous context has been compacted",
        "<current_focus>",
        "</current_focus>",
        "<environment>",
        "</environment>",
        "<completed_tasks>",
        "</completed_tasks>",
    ]
    return any(marker in text for marker in noise_markers)


def format_search_results(result: dict[str, Any]) -> str:
    """Format td-memory search result into a readable string."""
    if "results" not in result:
        return json.dumps(result, ensure_ascii=False, indent=2)
    results = result["results"]
    if isinstance(results, str):
        return results
    if not results:
        return "No matching memories found."
    lines = []
    for r in results:
        lines.append(f"- [{r.get('type', 'memory')}] {r.get('snippet', '(no preview)')}")
    return "\n".join(lines)
