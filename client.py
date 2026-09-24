"""HTTP client for TDAI Gateway (MemoryCore v2.0.0, v3 data plane)."""

from __future__ import annotations

import json
from typing import Any
from urllib import request, error

from config import gateway_url, gateway_api_key, service_id, identity_fields


def tdai_call(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make an HTTP call to TDAI Gateway and return the unwrapped JSON response.

    v3 endpoints answer with an envelope ``{code, message, request_id, data}``;
    this returns ``data`` and raises when ``code != 0``. Endpoints without an
    envelope (``GET /health``) are returned as-is.
    """
    url = gateway_url().rstrip("/") + path
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {
        "Content-Type": "application/json",
        "x-tdai-service-id": service_id(),
        # The v2/v3 router requires a non-empty Bearer token even when the
        # Gateway has no apiKey configured (the value is only verified when
        # the server sets one), so always send one.
        "Authorization": f"Bearer {gateway_api_key() or 'local'}",
    }

    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body) if body else {}
    except error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"TDAI Gateway error {e.code}: {body}") from e

    if "code" not in result:
        return result
    if result["code"] != 0:
        raise RuntimeError(
            f"TDAI Gateway error code={result['code']}: {result.get('message')} "
            f"(request_id={result.get('request_id')})"
        )
    data_field = result.get("data")
    return data_field if isinstance(data_field, dict) else {"data": data_field}


def health() -> dict[str, Any]:
    return tdai_call("GET", "/health")


def conversation_add(session_id: str, user_content: str, assistant_content: str) -> dict[str, Any]:
    """Write one user/assistant turn as L0; the server-side pipeline triggers
    L1/L2/L3 extraction automatically."""
    payload: dict[str, Any] = {
        "session_id": session_id,
        "messages": [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ],
    }
    payload.update(identity_fields())
    return tdai_call("POST", "/v3/conversation/add", payload)


def atomic_search(query: str, limit: int = 5) -> dict[str, Any]:
    """Search L1 atomic memories."""
    payload: dict[str, Any] = {"query": query, "limit": limit}
    payload.update(identity_fields())
    return tdai_call("POST", "/v3/atomic/search", payload)


def conversation_search(query: str, limit: int = 5, session_id: str | None = None) -> dict[str, Any]:
    """Search L0 raw conversations, optionally scoped to one session_id."""
    payload: dict[str, Any] = {"query": query, "limit": limit}
    if session_id:
        payload["session_id"] = session_id
    payload.update(identity_fields())
    return tdai_call("POST", "/v3/conversation/search", payload)


def scenario_ls(path_prefix: str = "") -> dict[str, Any]:
    """List L2 scenario entries (scene blocks)."""
    payload: dict[str, Any] = {"path_prefix": path_prefix}
    payload.update(identity_fields())
    return tdai_call("POST", "/v3/scenario/ls", payload)


def core_read() -> dict[str, Any]:
    """Read the L3 core memory (persona)."""
    payload: dict[str, Any] = {}
    payload.update(identity_fields())
    return tdai_call("POST", "/v3/core/read", payload)
