from __future__ import annotations

import json
import os
import socket
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .models import LabPaths
from .utils import ensure_parent, iso_now


class LockTimeoutError(TimeoutError):
    """Raised when a repository-local lock cannot be acquired in time."""


def _lock_age_seconds(path: Path) -> float:
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except FileNotFoundError:
        return 0.0


def _read_lock_payload(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _read_token(path: Path) -> str | None:
    value = _read_lock_payload(path)
    token = value.get("token") if value else None
    return token if isinstance(token, str) else None


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        # Windows and restricted containers may not expose a definitive answer.
        # Prefer preserving the lock over stealing it from a live process.
        return True
    return True


def _lock_can_be_reclaimed(path: Path, stale_after_seconds: float) -> bool:
    if stale_after_seconds <= 0 or _lock_age_seconds(path) < stale_after_seconds:
        return False
    payload = _read_lock_payload(path)
    if not payload:
        return True
    host = payload.get("host")
    pid = payload.get("pid")
    if host == socket.gethostname() and isinstance(pid, int):
        return not _pid_is_alive(pid)
    # A remote-host lock cannot be probed safely in the single-host harness.
    # Reclaim it only after the configured stale lease has elapsed.
    return True


@contextmanager
def file_lock(
    path: Path,
    *,
    timeout_seconds: float = 10.0,
    stale_after_seconds: float = 300.0,
    poll_seconds: float = 0.05,
) -> Iterator[None]:
    """Acquire an advisory cross-platform lock using atomic file creation.

    The lock lives in ignored repository-local state. ``O_EXCL`` is atomic on
    Windows and POSIX local filesystems, which is sufficient for the harness's
    single-host Planner/Executor model. A same-host lock is reclaimed only when
    its lease is old and the recorded owner process is no longer alive.
    """

    ensure_parent(path)
    token = uuid.uuid4().hex
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    payload = {
        "schema_version": 1,
        "token": token,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "created_at": iso_now(),
    }
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")

    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _lock_can_be_reclaimed(path, stale_after_seconds):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    # Another process may still own or be replacing the lock.
                    pass
                continue
            if time.monotonic() >= deadline:
                raise LockTimeoutError(f"Timed out waiting for lock {path}") from None
            time.sleep(max(0.01, poll_seconds))
            continue

        try:
            os.write(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        break

    try:
        yield
    finally:
        if _read_token(path) == token:
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def lab_lock(paths: LabPaths, name: str, **kwargs: float) -> Iterator[None]:
    safe_name = "".join(character if character.isalnum() or character in "-_." else "-" for character in name)
    return file_lock(paths.local / "locks" / f"{safe_name}.lock", **kwargs)
