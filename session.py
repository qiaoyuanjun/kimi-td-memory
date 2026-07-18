"""Project/session key resolution for kimi-td-memory."""

from __future__ import annotations

from pathlib import Path

from config import get_config


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
    project_root_str = str(project_root).lower()

    # Apply user-defined mappings first. Use longest matching pattern to avoid
    # accidental substring collisions (e.g. "budaogu" matching "budaogu-cloud").
    mappings = cfg.get("session_key_map", {})
    best_match: tuple[int, str] | None = None
    for pattern, session_key in mappings.items():
        pattern_lower = pattern.lower()
        if pattern_lower in project_root_str:
            if best_match is None or len(pattern_lower) > best_match[0]:
                best_match = (len(pattern_lower), session_key)

    if best_match is not None:
        return best_match[1]

    # Default: use project directory name + "-context"
    return f"{project_root.name}-context"
