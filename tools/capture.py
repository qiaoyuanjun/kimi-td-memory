#!/usr/bin/env python3
"""Plugin tool: td_capture — manually capture a user/assistant turn."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import resolve_session_key, capture


def main() -> None:
    try:
        params = json.load(sys.stdin)
        session_key = params.get("session_key") or resolve_session_key()
        user_content = params.get("user_content", "")
        assistant_content = params.get("assistant_content", "")

        if not user_content or not assistant_content:
            raise ValueError("user_content and assistant_content are required")

        result = capture(session_key, user_content, assistant_content)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
