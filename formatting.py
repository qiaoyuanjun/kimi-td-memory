"""Output formatting helpers for kimi-td-memory tools."""

from __future__ import annotations

import json
from typing import Any


def format_recall_result(result: dict[str, Any]) -> str:
    """Format td-memory /recall result into a readable string."""
    context = result.get("context")
    if isinstance(context, str) and context.strip():
        return context
    message = result.get("message")
    if isinstance(message, str) and message.strip():
        return message
    return json.dumps(result, ensure_ascii=False, indent=2)


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
