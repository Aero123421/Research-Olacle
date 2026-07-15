from __future__ import annotations

from typing import Any

from .bootstrap import materialize_repository_configuration
from .models import LabPaths
from .utils import atomic_write_json, iso_now, read_json, run_command


class RepositoryAdoptionError(RuntimeError):
    pass


def adopt_repository(
    paths: LabPaths,
    *,
    name_with_owner: str,
    visibility: str = "private",
    dry_run: bool = False,
    push: bool = True,
    materialize: bool = True,
) -> dict[str, Any]:
    if visibility not in {"private", "public", "internal"}:
        raise ValueError("visibility must be private, public, or internal")
    if "/" not in name_with_owner:
        raise ValueError("Repository must be OWNER/NAME")

    status = run_command(["git", "status", "--porcelain"], cwd=paths.root)
    if not status.ok:
        raise RepositoryAdoptionError(status.stderr or "Unable to read git status")
    # Discovery and interview state is ignored. Any tracked change here is an
    # unexpected mutation and must not be silently pushed to a new repository.
    if status.stdout.strip():
        raise RepositoryAdoptionError(
            "Tracked or unignored changes exist. Run init before adoption only with local state, "
            "or commit/stash unrelated changes."
        )

    old_origin = run_command(["git", "remote", "get-url", "origin"], cwd=paths.root)
    commands: list[list[str]] = []
    renamed_origin = False
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
        try:
            if old_origin.ok:
                result = run_command(commands[0], cwd=paths.root, timeout=30)
                if not result.ok:
                    raise RepositoryAdoptionError(
                        f"Command failed: {' '.join(commands[0])}\n{result.stderr or result.stdout}"
                    )
                renamed_origin = True
            result = run_command(create, cwd=paths.root, timeout=120)
            if not result.ok:
                raise RepositoryAdoptionError(
                    f"Command failed: {' '.join(create)}\n{result.stderr or result.stdout}"
                )
        except Exception:
            # Keep adoption retryable when GitHub creation fails after renaming
            # the template remote.
            if renamed_origin:
                current_origin = run_command(["git", "remote", "get-url", "origin"], cwd=paths.root)
                if not current_origin.ok:
                    run_command(
                        ["git", "remote", "rename", "template-upstream", "origin"],
                        cwd=paths.root,
                    )
            raise

    state = {
        "schema_version": 1,
        "repository": name_with_owner,
        "visibility": visibility,
        "template_upstream": old_origin.stdout if old_origin.ok else None,
        "adopted_at": iso_now(),
        "dry_run": dry_run,
        "commands": commands,
        "materialized_files": [],
    }
    paths.ensure_runtime()
    atomic_write_json(paths.local / "repository.json", state)

    if not dry_run and materialize:
        answers = read_json(paths.local / "answers.json", default={})
        instance = read_json(paths.local / "instance.json", default={})
        if isinstance(answers, dict) and answers and isinstance(instance, dict) and instance:
            files = materialize_repository_configuration(paths, answers=answers, instance=instance)
            instance["materialized"] = True
            instance["materialized_at"] = iso_now()
            instance["updated_at"] = instance["materialized_at"]
            atomic_write_json(paths.local / "instance.json", instance)
            state["materialized_files"] = files
            atomic_write_json(paths.local / "repository.json", state)

    return state
