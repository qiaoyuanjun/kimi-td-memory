#!/usr/bin/env python3
"""Auto-capture watcher for kimi-td-memory.

Watches Kimi Code CLI session files under ~/.kimi-code/sessions/ and feeds
user/assistant turns into TDAI Gateway (td-memory) automatically.

Session files are event streams (``<session>/agents/main/wire.jsonl``):

- user messages arrive as ``context.append_message`` events with
  ``message.role == "user"`` and ``message.origin.kind == "user"``
  (``origin.kind == "injection"`` marks CLI-injected messages, skipped);
- assistant text arrives as ``context.append_loop_event`` events with
  ``event.type == "content.part"`` and ``part.type == "text"``, grouped by
  ``event.turnId`` (``think`` parts and tool events are skipped).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import signal
import sys
import time
from pathlib import Path
from typing import Any

from client import capture, end_session, health
from config import gateway_url, get_config, get_watcher_state_dir
from session import find_project_root, resolve_session_key
from text import extract_text, is_system_noise, strip_system_reminders


def setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("td-watcher")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        logger.handlers.clear()
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


class WatcherState:
    def __init__(self, state_path: Path):
        self.state_path = state_path
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"files": {}, "sessions": {}}

    def save(self) -> None:
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_file_state(self, path: Path) -> dict[str, Any]:
        return self.data["files"].setdefault(str(path), {"pos": 0, "seen": []})

    def get_session_state(self, session_key: str) -> dict[str, Any]:
        return self.data["sessions"].setdefault(session_key, {"last_capture": None, "ended": False})

    def mark_seen(self, path: Path, digest: str) -> None:
        fs = self.get_file_state(path)
        seen = fs.setdefault("seen", [])
        seen.append(digest)
        # Keep last 1000 digests
        fs["seen"] = seen[-1000:]

    def is_seen(self, path: Path, digest: str) -> bool:
        return digest in self.get_file_state(path).get("seen", [])

    def update_pos(self, path: Path, pos: int) -> None:
        self.get_file_state(path)["pos"] = pos

    def update_last_capture(self, session_key: str) -> None:
        self.get_session_state(session_key)["last_capture"] = time.time()
        self.get_session_state(session_key)["ended"] = False

    def mark_ended(self, session_key: str) -> None:
        self.get_session_state(session_key)["ended"] = True


class SessionWatcher:
    def __init__(self, logger: logging.Logger | None = None):
        self.cfg = get_config()
        self.running = True
        state_dir = get_watcher_state_dir()
        self.state = WatcherState(state_dir / "watcher-state.json")
        self.pid_file = state_dir / "watcher.pid"
        self.log_path = state_dir / "watcher.log"
        self.logger = logger or setup_logging(self.log_path)
        self.poll_interval = int(self.cfg.get("watcher", {}).get("poll_interval", 5))
        self.idle_timeout = int(self.cfg.get("watcher", {}).get("idle_timeout", 300))
        # How long an unfinished assistant turn may sit idle before it is
        # flushed and captured anyway (handles the final turn of a session).
        self.flush_delay = int(self.cfg.get("watcher", {}).get("flush_delay", 30))
        kimi_home = os.environ.get("KIMI_CODE_HOME")
        self.session_dir = (Path(kimi_home) if kimi_home else Path.home() / ".kimi-code") / "sessions"

    def write_pid(self) -> None:
        self.pid_file.write_text(str(os.getpid()))

    def remove_pid(self) -> None:
        if self.pid_file.exists():
            try:
                self.pid_file.unlink()
            except Exception:
                pass

    def discover_wire_files(self) -> list[Path]:
        """Find all main-agent wire.jsonl files under the Kimi Code sessions dir."""
        if not self.session_dir.exists():
            return []
        files = []
        for workspace_dir in self.session_dir.iterdir():
            if not workspace_dir.is_dir():
                continue
            for session_dir in workspace_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                wire = session_dir / "agents" / "main" / "wire.jsonl"
                if wire.exists():
                    files.append(wire)
        return files

    @staticmethod
    def _clean_text(text: str | None) -> str | None:
        """Strip CLI-injected reminders and system noise; None if nothing left."""
        if not text:
            return None
        text = strip_system_reminders(text).strip()
        if not text or is_system_noise(text):
            return None
        return text

    def _parse_user_message(self, obj: dict[str, Any]) -> str | None:
        msg = obj.get("message") or {}
        if msg.get("role") != "user":
            return None
        origin = msg.get("origin") or {}
        # Only real user input; skip plan-mode/system injections.
        if origin.get("kind") != "user":
            return None
        return self._clean_text(extract_text(msg.get("content")))

    def _close_turn(self, path: Path) -> list[tuple[str, str]]:
        """Close the buffered assistant turn and pair it with the pending user message."""
        fs = self.state.get_file_state(path)
        parts = fs.get("turn_parts") or []
        fs["turn_parts"] = []
        fs["turn_id"] = None
        if not parts:
            # No assistant text buffered (e.g. the turn only started thinking,
            # or consisted solely of tool calls). Keep pending_user so it can
            # still pair with the next turn that produces text.
            return []
        user = fs.get("pending_user")
        fs["pending_user"] = None
        if not user:
            return []
        assistant = "\n".join(parts)
        digest = hashlib.sha256(f"{user}\n{assistant}".encode("utf-8")).hexdigest()[:32]
        if self.state.is_seen(path, digest):
            return []
        self.state.mark_seen(path, digest)
        return [(user, assistant)]

    def _feed_event(self, path: Path, obj: dict[str, Any]) -> list[tuple[str, str]]:
        """Feed one wire.jsonl event; return any completed (user, assistant) pairs."""
        pairs: list[tuple[str, str]] = []
        fs = self.state.get_file_state(path)
        etype = obj.get("type")
        if etype == "context.append_message":
            # A new message closes any open assistant turn.
            pairs += self._close_turn(path)
            user_text = self._parse_user_message(obj)
            if user_text:
                fs["pending_user"] = user_text
        elif etype == "context.append_loop_event":
            event = obj.get("event") or {}
            if event.get("type") == "content.part":
                turn_id = event.get("turnId")
                if turn_id is not None and turn_id != fs.get("turn_id"):
                    pairs += self._close_turn(path)
                    fs["turn_id"] = turn_id
                part = event.get("part") or {}
                if part.get("type") == "text":
                    text = self._clean_text(str(part.get("text") or ""))
                    if text:
                        fs.setdefault("turn_parts", []).append(text)
                        fs["turn_updated"] = time.time()
        return pairs

    def read_new_pairs(self, path: Path) -> list[tuple[str, str]]:
        """Read events appended since the last poll and return completed pairs."""
        fs = self.state.get_file_state(path)
        last_pos = fs.get("pos", 0)
        pairs: list[tuple[str, str]] = []

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size < last_pos:
                # File was truncated/rotated
                last_pos = 0
            f.seek(last_pos)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                pairs += self._feed_event(path, obj)
            new_pos = f.tell()

        self.state.update_pos(path, new_pos)
        return pairs

    def flush_stale_turns(self) -> list[tuple[Path, str, str]]:
        """Close assistant turns idle longer than flush_delay.

        A turn normally closes when the next user message or turn arrives;
        the final turn of a session needs this timeout-based flush.
        """
        now = time.time()
        flushed: list[tuple[Path, str, str]] = []
        for key, fs in list(self.state.data["files"].items()):
            if not (fs.get("turn_parts") or []):
                continue
            updated = fs.get("turn_updated") or 0
            if now - updated < self.flush_delay:
                continue
            path = Path(key)
            for user, assistant in self._close_turn(path):
                flushed.append((path, user, assistant))
        return flushed

    def _match_session_key_map(self, workspace_key: str) -> str | None:
        """Longest session_key_map pattern contained in the workspace dir name."""
        mappings = self.cfg.get("session_key_map", {})
        key_lower = workspace_key.lower()
        best: tuple[int, str] | None = None
        for pattern, session_key in mappings.items():
            pattern_lower = pattern.lower()
            if pattern_lower in key_lower:
                if best is None or len(pattern_lower) > best[0]:
                    best = (len(pattern_lower), session_key)
        return best[1] if best else None

    def resolve_session_key_for_file(self, path: Path) -> str:
        """Resolve td-memory session_key from the Kimi Code workspace dir name.

        Kimi Code stores sessions as:
          ~/.kimi-code/sessions/<workspace_key>/<session_id>/agents/main/wire.jsonl
        where workspace_key looks like ``wd_<project-dir-name>_<hash>``. The
        project name is stable across sessions for the same workspace, so we
        use it as the session_key prefix for cross-session memory.
        """
        try:
            rel = path.resolve().relative_to(self.session_dir.resolve())
            parts = rel.parts
            if len(parts) >= 1:
                workspace_key = parts[0]
                mapped = self._match_session_key_map(workspace_key)
                if mapped:
                    return mapped
                m = re.match(r"^wd_(.+)_[0-9a-fA-F]{8,16}$", workspace_key)
                if m:
                    return f"{m.group(1)}-context"
                return f"{workspace_key}-context"
        except Exception:
            pass
        # Fallback to project-root based naming
        project_root = find_project_root(path.parent)
        return resolve_session_key(project_root)

    def _capture_pairs(self, path: Path, pairs: list[tuple[str, str]]) -> None:
        if not pairs:
            return
        session_key = self.resolve_session_key_for_file(path)
        for user_text, assistant_text in pairs:
            try:
                result = capture(session_key, user_text, assistant_text)
                self.logger.info(f"captured: session={session_key} l0_recorded={result.get('l0_recorded', 0)}")
                self.state.update_last_capture(session_key)
            except Exception as e:
                self.logger.error(f"capture failed: {e}")

    def process_file(self, path: Path) -> None:
        self._capture_pairs(path, self.read_new_pairs(path))

    def check_idle_sessions(self) -> None:
        now = time.time()
        for session_key, sess in list(self.state.data["sessions"].items()):
            if sess.get("ended"):
                continue
            last = sess.get("last_capture")
            if last and (now - last) > self.idle_timeout:
                try:
                    end_session(session_key)
                    self.logger.info(f"ended idle session: {session_key}")
                    self.state.mark_ended(session_key)
                except Exception as e:
                    self.logger.error(f"end_session failed: {e}")

    def run(self) -> None:
        self.logger.info(f"started. gateway={gateway_url()} poll={self.poll_interval}s idle={self.idle_timeout}s")
        self.logger.info(f"watching: {self.session_dir}")
        self.write_pid()

        try:
            while self.running:
                try:
                    for path in self.discover_wire_files():
                        self.process_file(path)
                    for path, user_text, assistant_text in self.flush_stale_turns():
                        self._capture_pairs(path, [(user_text, assistant_text)])
                    self.check_idle_sessions()
                    self.state.save()
                except Exception as e:
                    self.logger.error(f"loop error: {e}")
                time.sleep(self.poll_interval)
        finally:
            self.state.save()
            self.remove_pid()
            self.logger.info("stopped.")


def stop_self() -> None:
    """Stop the currently running watcher (used by ``python watcher.py stop``)."""
    state_dir = get_watcher_state_dir()
    pid_file = state_dir / "watcher.pid"
    log_path = state_dir / "watcher.log"
    logger = setup_logging(log_path)
    if not pid_file.exists():
        logger.info("stop requested but watcher is not running")
        print("[td-watcher] not running")
        return
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        logger.info(f"sent SIGTERM to PID {pid}")
        print(f"[td-watcher] sent SIGTERM to PID {pid}")
    except Exception as e:
        logger.error(f"stop failed: {e}")
        print(f"[td-watcher] stop failed: {e}", file=sys.stderr)


def main() -> None:
    state_dir = get_watcher_state_dir()
    log_path = state_dir / "watcher.log"
    logger = setup_logging(log_path)

    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop_self()
        return

    # Health check before starting
    try:
        health()
    except Exception as e:
        logger.error(f"gateway not reachable: {e}")
        print(f"[td-watcher] gateway not reachable: {e}", file=sys.stderr)
        print("[td-watcher] please start TDAI Gateway first.", file=sys.stderr)
        sys.exit(1)

    watcher = SessionWatcher(logger=logger)

    def handle_signal(signum, frame):
        logger.info(f"received signal {signum}")
        watcher.running = False

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    watcher.run()


if __name__ == "__main__":
    main()
