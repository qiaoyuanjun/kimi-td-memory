"""HTTP client for TDAI Gateway."""

from __future__ import annotations

import json
from typing import Any
from urllib import request, error

from config import gateway_url, gateway_api_key


def tdai_call(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make an HTTP call to TDAI Gateway and return JSON response."""
    url = gateway_url().rstrip("/") + path
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"}
    api_key = gateway_api_key()
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


def recall(session_key: str, query: str) -> dict[str, Any]:
    """Recall top-layer memory context (L3 persona + L2 scene navigation + L1 hints)."""
    return tdai_call(
        "POST",
        "/recall",
        {"session_key": session_key, "query": query},
    )


def search_conversations(session_key: str, query: str, limit: int = 5) -> dict[str, Any]:
    return tdai_call(
        "POST",
        "/search/conversations",
        {"session_id": session_key, "query": query, "limit": limit},
    )


def health() -> dict[str, Any]:
    return tdai_call("GET", "/health")
