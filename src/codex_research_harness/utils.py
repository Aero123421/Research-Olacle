from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
import textwrap
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    ensure_parent(path)
    normalized = text.replace("\r\n", "\n")
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding=encoding,
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(normalized)
        temp_name = handle.name
    os.replace(temp_name, path)


def atomic_write_json(path: Path, value: Any, *, indent: int = 2) -> None:
    if is_dataclass(value):
        value = asdict(value)
    atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=indent, sort_keys=True) + "\n",
    )


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError as exc:  # pragma: no cover - Python >=3.11 required
        raise RuntimeError("Python 3.11 or later is required") from exc
    with path.open("rb") as handle:
        return tomllib.load(handle)


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() or (candidate / ".research-lab").exists():
            return candidate
    raise FileNotFoundError("Could not find a repository root containing .git or .research-lab")


def slugify(value: str, *, max_length: int = 64) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    cleaned = re.sub(r"-+", "-", cleaned).lower()
    return (cleaned or "research")[0:max_length].rstrip("-._")


def word_count(text: str) -> int:
    # Works reasonably for English and whitespace-delimited Japanese fragments;
    # character budgets are tracked separately where precise control is needed.
    return len(re.findall(r"\S+", text))


def truncate_text(text: str, *, max_chars: int, marker: str = "\n…[truncated]\n") -> str:
    if len(text) <= max_chars:
        return text
    keep = max(0, max_chars - len(marker))
    return text[:keep].rstrip() + marker


def human_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "unknown"
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def command_display(command: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return shlex.join(command)


class CommandResult:
    def __init__(
        self,
        command: Sequence[str],
        returncode: int,
        stdout: str,
        stderr: str,
        duration_seconds: float,
        timed_out: bool = False,
    ) -> None:
        self.command = tuple(command)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.duration_seconds = duration_seconds
        self.timed_out = timed_out

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": list(self.command),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": round(self.duration_seconds, 3),
            "timed_out": self.timed_out,
            "ok": self.ok,
        }


def run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float = 20.0,
    env: Mapping[str, str] | None = None,
    input_text: str | None = None,
) -> CommandResult:
    start = datetime.now(UTC)
    merged_env = os.environ.copy()
    if env:
        merged_env.update({str(k): str(v) for k, v in env.items()})
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd) if cwd else None,
            env=merged_env,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            errors="replace",
        )
        duration = (datetime.now(UTC) - start).total_seconds()
        return CommandResult(
            command,
            completed.returncode,
            completed.stdout.strip(),
            completed.stderr.strip(),
            duration,
        )
    except FileNotFoundError as exc:
        duration = (datetime.now(UTC) - start).total_seconds()
        return CommandResult(command, 127, "", str(exc), duration)
    except subprocess.TimeoutExpired as exc:
        duration = (datetime.now(UTC) - start).total_seconds()
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return CommandResult(command, 124, stdout.strip(), stderr.strip(), duration, True)


def first_nonempty(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None


def markdown_table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    header_line = "| " + " | ".join(str(h) for h in headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |" for row in rows]
    return "\n".join([header_line, separator, *body])


def dedent(value: str) -> str:
    return textwrap.dedent(value).strip() + "\n"


def safe_relpath(path: Path, root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError as exc:
        raise ValueError(f"Path {resolved_path} is outside repository root {resolved_root}") from exc
