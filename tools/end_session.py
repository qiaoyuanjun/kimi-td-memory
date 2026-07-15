#!/usr/bin/env python3
"""Plugin tool: td_end_session — flush session and trigger L1/L2/L3 extraction."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import resolve_session_key, end_session


def main() -> None:
    try:
        params = json.load(sys.stdin)
        session_key = params.get("session_key") or resolve_session_key()

        result = end_session(session_key)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
