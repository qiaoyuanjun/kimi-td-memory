#!/usr/bin/env python3
"""Plugin tool: td_search_conversations — search L0 raw conversations."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import resolve_session_key, search_conversations, format_search_results


def main() -> None:
    try:
        params = json.load(sys.stdin)
        query = params.get("query", "")
        limit = min(int(params.get("limit", 5)), 20)
        session_key = params.get("session_key") or resolve_session_key()

        result = search_conversations(session_key, query, limit)
        print(format_search_results(result))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
