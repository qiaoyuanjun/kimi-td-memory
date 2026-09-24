"""Direct local-file access to the MemoryCore data dir.

L2 scene blocks and the L3 persona are plain Markdown files under
``<data_dir>/profiles/team%3A<team>%7Cagent%3A<agent>/`` — reading them from
disk avoids the Gateway roundtrip entirely and works even when the Gateway
is down. L0/L1 live in SQLite and still go through the API (BM25/embedding
ranking lives server-side).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from config import data_dir


def _profile_root(team_id: str, agent_id: str) -> Path | None:
    base = data_dir()
    if not base:
        return None
    scope = quote(f"team:{team_id}|agent:{agent_id}", safe="")
    root = Path(base) / "profiles" / scope
    return root if root.is_dir() else None


def read_persona(team_id: str = "default", agent_id: str = "default") -> str | None:
    """Read persona.md content; None when the local profile is unavailable."""
    root = _profile_root(team_id, agent_id)
    if not root:
        return None
    persona = root / "persona.md"
    if not persona.is_file():
        return None
    try:
        return persona.read_text(encoding="utf-8")
    except Exception:
        return None


def _parse_meta(text: str) -> dict[str, str]:
    """Parse the -----META-START-----/-----META-END----- header of a scene block."""
    meta: dict[str, str] = {}
    if not text.startswith("-----META-START-----"):
        return meta
    end = text.find("-----META-END-----")
    if end < 0:
        return meta
    for line in text[len("-----META-START-----"):end].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta


def list_scene_blocks(team_id: str = "default", agent_id: str = "default") -> list[dict[str, Any]] | None:
    """List scene blocks as scenario/ls-shaped entries with absolute paths.

    Returns None when the local profile is unavailable (caller falls back to
    the API).
    """
    root = _profile_root(team_id, agent_id)
    if not root:
        return None
    blocks_dir = root / "scene_blocks"
    if not blocks_dir.is_dir():
        return None
    entries: list[dict[str, Any]] = []
    for f in sorted(blocks_dir.glob("*.md")):
        try:
            meta = _parse_meta(f.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        entry: dict[str, Any] = {
            "path": str(f),
            "summary": meta.get("summary"),
            "updated_at": meta.get("updated"),
        }
        if meta.get("heat"):
            try:
                entry["heat"] = int(meta["heat"])
            except ValueError:
                pass
        entries.append(entry)
    return entries
