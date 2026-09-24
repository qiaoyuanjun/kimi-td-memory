#!/usr/bin/env python3
"""Bootstrap v3 metadata entities required by the Skill module.

Skill creation (manual or pipeline extraction) auto-registers a metadata
asset, which requires the owning (team, agent) to exist in the v3 metadata
store. Chat memory (L0-L3) does NOT need this and keeps using the default
bucket — this script provisions a separate identity used only for skills.

Idempotent: safe to re-run; existing entities are reused.

Usage: python scripts/bootstrap_skill.py
Writes back into ~/.kimi-td-memory/config.json:
  skill_identity: {team_id, agent_id, user_id}
  admin_key / user_key (kept for future re-provisioning)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from client import tdai_call
from config import get_config

USER_CONFIG = Path.home() / ".kimi-td-memory" / "config.json"

BOOTSTRAP_USERNAME = "kimi"
TEAM_NAME = "kimi-code"
AGENT_NAME = "kimi"


def meta_call(path: str, payload: dict, user_key: str | None = None) -> dict:
    """Call a /v3/meta route; user_key goes to the x-tdai-user-key header."""
    # tdai_call has no per-call header override, so do it inline here.
    import json as _json
    from urllib import request, error
    from config import gateway_url, gateway_api_key, service_id

    url = gateway_url().rstrip("/") + path
    data = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-tdai-service-id": service_id(),
        "Authorization": f"Bearer {gateway_api_key() or 'local'}",
    }
    if user_key:
        headers["x-tdai-user-key"] = user_key
    req = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=60) as resp:
            result = _json.loads(resp.read().decode("utf-8") or "{}")
    except error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"meta call {path} failed {e.code}: {body}") from e
    if result.get("code", 0) != 0:
        raise RuntimeError(f"meta call {path} error code={result.get('code')}: {result.get('message')}")
    return result.get("data") or {}


def save_config(patch: dict) -> None:
    cfg = {}
    if USER_CONFIG.exists():
        cfg = json.loads(USER_CONFIG.read_text(encoding="utf-8"))
    cfg.update(patch)
    USER_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    USER_CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    cfg = get_config()
    admin_key = cfg.get("admin_key") or ""

    if not admin_key:
        try:
            data = meta_call("/v3/internal/meta/user/init-admin", {"username": "admin"})
            admin_key = data["user_key"]
            save_config({"admin_key": admin_key})
            print("[bootstrap] admin initialized")
        except RuntimeError as e:
            if "already_initialized" in str(e):
                print("[bootstrap] ERROR: admin already initialized but no admin_key in config.", file=sys.stderr)
                print("  Put the admin user_key into ~/.kimi-td-memory/config.json as \"admin_key\" and re-run.", file=sys.stderr)
                sys.exit(1)
            raise

    # --- business user ---
    user_key = cfg.get("user_key") or ""
    user_id = ""
    if user_key:
        data = meta_call("/v3/meta/auth/verify", {"user_key": user_key})
        if data.get("valid"):
            user_id = data["user"]["user_id"]
    if not user_id:
        data = meta_call("/v3/meta/user/create", {"username": BOOTSTRAP_USERNAME}, user_key=admin_key)
        user_id = data["user_id"]
        user_key = data["default_user_key"]
        save_config({"user_key": user_key})
        print(f"[bootstrap] user created: {user_id}")
    else:
        print(f"[bootstrap] user reused: {user_id}")

    # --- team ---
    team_id = ""
    data = meta_call("/v3/meta/team/list", {"user_id": user_id, "limit": 100}, user_key=user_key)
    for t in data.get("items", []):
        if t.get("name") == TEAM_NAME:
            team_id = t["team_id"]
            break
    if not team_id:
        data = meta_call(
            "/v3/meta/team/create",
            {"name": TEAM_NAME, "owner_user_id": user_id, "description": "Kimi Code skill assets"},
            user_key=user_key,
        )
        team_id = data["team_id"]
        print(f"[bootstrap] team created: {team_id}")
    else:
        print(f"[bootstrap] team reused: {team_id}")

    # --- agent ---
    agent_id = ""
    data = meta_call("/v3/meta/agent/list", {"team_id": team_id, "limit": 100}, user_key=user_key)
    for a in data.get("items", []):
        if a.get("name") == AGENT_NAME:
            agent_id = a["agent_id"]
            break
    if not agent_id:
        data = meta_call(
            "/v3/meta/agent/create",
            {
                "team_id": team_id,
                "owner_user_id": user_id,
                "name": AGENT_NAME,
                "description": "Kimi Code 对话沉淀的 Skill 资产归属 agent",
            },
            user_key=user_key,
        )
        agent_id = data["agent_id"]
        print(f"[bootstrap] agent created: {agent_id}")
    else:
        print(f"[bootstrap] agent reused: {agent_id}")

    save_config({
        "skill_identity": {"team_id": team_id, "agent_id": agent_id, "user_id": user_id},
    })
    print(f"[bootstrap] skill_identity written to {USER_CONFIG}")


if __name__ == "__main__":
    main()
