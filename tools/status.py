#!/usr/bin/env python3
"""Plugin tool: td_status — show watcher status."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import gateway_url


def main() -> None:
    try:
        params = json.load(sys.stdin)
        watcher_pid_file = Path("~/.kimi-td-memory/watcher.pid").expanduser()
        running = watcher_pid_file.exists()
        pid = None
        if running:
            try:
                pid = int(watcher_pid_file.read_text().strip())
            except Exception:
                pass

        print(
            json.dumps(
                {
                    "gateway_url": gateway_url(),
                    "watcher_running": running,
                    "watcher_pid": pid,
                    "watcher_pid_file": str(watcher_pid_file),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
