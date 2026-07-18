"""Text extraction and filtering helpers for Kimi Code wire.jsonl data."""

from __future__ import annotations

import re
from typing import Any

_SYSTEM_REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)


def strip_system_reminders(text: str) -> str:
    """Remove <system-reminder>...</system-reminder> blocks injected by the CLI."""
    return _SYSTEM_REMINDER_RE.sub("", text)


def extract_text(content: Any) -> str:
    """Extract plain text from a Kimi Code message content field."""
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
