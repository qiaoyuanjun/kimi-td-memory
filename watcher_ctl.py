"""Watcher lifecycle management for kimi-td-memory."""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from client import health
from config import get_watcher_pid_file, get_watcher_state_dir


def _process_exists(pid: int) -> bool:
    """Check whether a process with the given PID exists."""
    if os.name == "nt":  # Windows
        try:
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    else:  # Unix-like
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True


def is_watcher_running() -> bool:
    """Check whether the watcher process is currently running."""
    pid_file = get_watcher_pid_file()
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception:
        return False
    if _process_exists(pid):
        return True
    # Stale PID file; clean it up
    try:
        pid_file.unlink()
    except Exception:
        pass
    return False


def start_watcher(*, skip_health_check: bool = False) -> dict[str, Any]:
    """Start the watcher as a detached background process.

    Returns a dict with at least ``started`` (bool). On success also includes
    ``pid``; on failure includes ``error``.
    """
    if is_watcher_running():
        return {"started": False, "running": True, "error": "watcher is already running"}

    # Gateway must be reachable before starting the watcher.
    if not skip_health_check:
        try:
            health()
        except Exception as e:
            return {"started": False, "running": False, "error": f"gateway not reachable: {e}"}

    state_dir = get_watcher_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)

    # Use a simple lock file to prevent concurrent starts from racing.
    lock_file = state_dir / "watcher-start.lock"
    try:
        # Exclusive creation fails if lock already exists.
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.close(fd)
        except Exception:
            pass
    except FileExistsError:
        # Another process is starting the watcher; wait briefly and recheck.
        for _ in range(15):
            if is_watcher_running():
                return {"started": False, "running": True, "error": "watcher started by another process"}
            time.sleep(0.2)
        return {"started": False, "running": False, "error": "watcher start lock is held"}

    try:
        # Double-check after acquiring lock.
        if is_watcher_running():
            return {"started": False, "running": True, "error": "watcher is already running"}

        watcher_script = Path(__file__).parent.resolve() / "watcher.py"
        if not watcher_script.exists():
            return {"started": False, "running": False, "error": f"watcher script not found: {watcher_script}"}

        kwargs: dict[str, Any] = {}
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            kwargs["start_new_session"] = True

        with open(os.devnull, "r") as devnull_in, open(os.devnull, "w") as devnull_out:
            process = subprocess.Popen(
                [sys.executable, str(watcher_script)],
                stdin=devnull_in,
                stdout=devnull_out,
                stderr=subprocess.STDOUT,
                close_fds=True,
                **kwargs,
            )

        # Wait briefly for the watcher to write its PID file.
        for _ in range(25):
            if is_watcher_running():
                return {"started": True, "running": True, "pid": process.pid}
            time.sleep(0.1)

        return {"started": False, "running": False, "error": "watcher did not start in time"}
    finally:
        try:
            if lock_file.exists():
                lock_file.unlink()
        except Exception:
            pass


def stop_watcher(*, timeout: float = 5.0) -> dict[str, Any]:
    """Stop the watcher process.

    First attempts a graceful termination, then falls back to force kill if
    the process does not exit within ``timeout`` seconds.
    """
    pid_file = get_watcher_pid_file()
    if not pid_file.exists():
        return {"stopped": False, "error": "watcher is not running"}
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception as e:
        return {"stopped": False, "error": f"invalid PID file: {e}"}

    if not _process_exists(pid):
        try:
            pid_file.unlink()
        except Exception:
            pass
        return {"stopped": True, "pid": pid, "note": "process was already gone"}

    # Try graceful termination first.
    try:
        if os.name == "nt":
            os.kill(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except Exception as e:
        return {"stopped": False, "error": f"failed to send signal: {e}"}

    # Wait for graceful exit.
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _process_exists(pid):
            try:
                if pid_file.exists():
                    pid_file.unlink()
            except Exception:
                pass
            return {"stopped": True, "pid": pid, "graceful": True}
        time.sleep(0.1)

    # Force kill if still running.
    if os.name == "nt":
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(1, False, pid)  # PROCESS_TERMINATE
            if handle:
                kernel32.TerminateProcess(handle, 0)
                kernel32.CloseHandle(handle)
        except Exception as e:
            return {"stopped": False, "error": f"failed to terminate process: {e}"}
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception as e:
            return {"stopped": False, "error": f"failed to force kill: {e}"}

    # Clean up PID file if still present.
    try:
        if pid_file.exists():
            pid_file.unlink()
    except Exception:
        pass

    return {"stopped": True, "pid": pid, "graceful": False}


def ensure_watcher() -> dict[str, Any]:
    """Ensure watcher is running; start it if not.

    This function is designed to be safe to call from any tool: it never
    raises and only attempts to start the watcher when it is not running.
    """
    try:
        if is_watcher_running():
            return {"running": True, "started": False}
        return start_watcher()
    except Exception as e:
        return {"running": False, "started": False, "error": str(e)}
