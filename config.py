"""Configuration loading and accessors for kimi-td-memory."""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path
from typing import Any


@functools.lru_cache(maxsize=1)
def get_config() -> dict[str, Any]:
    """Load plugin configuration.

    A user-level config at ``~/.kimi-td-memory/config.json`` takes precedence
    over the config.json bundled with the plugin. This matters because the
    CLI runs the managed copy under ``plugins/managed/<id>/``: edits to the
    source directory's config.json only take effect after a reinstall, while
    the user-level file survives reinstalls.

    The result is cached for the lifetime of the process to avoid repeated
    disk reads on every tool invocation.
    """
    user_config = Path.home() / ".kimi-td-memory" / "config.json"
    bundled_config = Path(__file__).parent.resolve() / "config.json"
    for config_path in (user_config, bundled_config):
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    return {}


def gateway_url() -> str:
    """Return TDAI Gateway URL from env or config.json."""
    url = os.environ.get("TDAI_GATEWAY_URL") or get_config().get("gateway_url")
    if not url:
        raise RuntimeError(
            "TDAI Gateway URL is not configured. "
            "Set TDAI_GATEWAY_URL environment variable, "
            "or set gateway_url in config.json."
        )
    return url


def gateway_api_key() -> str:
    """Return Gateway API key from env or config.json."""
    return os.environ.get("TDAI_GATEWAY_API_KEY") or get_config().get("gateway_api_key") or ""


def get_watcher_state_dir() -> Path:
    """Return watcher state directory from config or default."""
    cfg = get_config()
    state_dir = cfg.get("watcher", {}).get("state_dir", "~/.kimi-td-memory")
    return Path(state_dir).expanduser()


def get_watcher_pid_file() -> Path:
    """Return path to watcher PID file."""
    return get_watcher_state_dir() / "watcher.pid"
