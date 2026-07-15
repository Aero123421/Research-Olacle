from __future__ import annotations

from typing import Any

from .models import LabPaths
from .utils import atomic_write_json, iso_now, run_command


class RepositoryAdoptionError(RuntimeError):
    pass


def adopt_repository(
    paths: LabPaths,
    *,
    name_with_owner: str,
    visibility: str = "private",
    dry_run: bool = False,
    push: bool = True,
) -> dict[str, Any]:
    if visibility not in {"private", "public", "internal"}:
        raise ValueError("visibility must be private, public, or internal")
    if "/" not in name_with_owner:
        raise ValueError("Repository must be OWNER/NAME")
    status = run_command(["git", "status", "--porcelain"], cwd=paths.root)
    if not status.ok:
        raise RepositoryAdoptionError(status.stderr or "Unable to read git status")
    # Template files are expected to be committed before adoption. A dirty tree
    # is dangerous because `gh repo create --push` may omit intended content.
    if status.stdout.strip():
        raise RepositoryAdoptionError("Commit or stash local changes before adopting the template")
    old_origin = run_command(["git", "remote", "get-url", "origin"], cwd=paths.root)
    commands: list[list[str]] = []
    if old_origin.ok:
        commands.append(["git", "remote", "rename", "origin", "template-upstream"])
    create = [
        "gh",
        "repo",
        "create",
        name_with_owner,
        f"--{visibility}",
        "--source",
        ".",
        "--remote",
        "origin",
    ]
    if push:
        create.append("--push")
    commands.append(create)
    if not dry_run:
        for command in commands:
            result = run_command(command, cwd=paths.root, timeout=120)
            if not result.ok:
                raise RepositoryAdoptionError(
                    f"Command failed: {' '.join(command)}\n{result.stderr or result.stdout}"
                )
    state = {
        "schema_version": 1,
        "repository": name_with_owner,
        "visibility": visibility,
        "template_upstream": old_origin.stdout if old_origin.ok else None,
        "adopted_at": iso_now(),
        "dry_run": dry_run,
        "commands": commands,
    }
    paths.ensure_runtime()
    atomic_write_json(paths.local / "repository.json", state)
    return state
