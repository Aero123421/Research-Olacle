from __future__ import annotations

from typing import Any

from .models import LabPaths
from .utils import deep_merge, read_json, read_toml


class ConfigError(RuntimeError):
    pass


def load_lab_config(paths: LabPaths) -> dict[str, Any]:
    default_path = paths.lab / "config" / "lab.toml"
    local_path = paths.local / "lab.toml"
    return deep_merge(read_toml(default_path), read_toml(local_path))


def load_agent_config(paths: LabPaths) -> dict[str, Any]:
    defaults = read_toml(paths.lab / "config" / "agents.toml")
    local = read_toml(paths.local / "agents.toml")
    return deep_merge(defaults, local)


def load_compute_config(paths: LabPaths) -> dict[str, Any]:
    defaults = read_toml(paths.lab / "config" / "compute.toml")
    local = read_toml(paths.local / "compute.toml")
    return deep_merge(defaults, local)


def load_context_config(paths: LabPaths) -> dict[str, Any]:
    defaults = read_toml(paths.lab / "config" / "context.toml")
    local = read_toml(paths.local / "context.toml")
    return deep_merge(defaults, local)


def load_project_spec(paths: LabPaths) -> dict[str, Any]:
    spec = read_json(paths.lab / "project-spec.json", default={})
    if not isinstance(spec, dict) or "fields" not in spec:
        raise ConfigError("Invalid .research-lab/project-spec.json")
    return spec


def load_instance(paths: LabPaths) -> dict[str, Any]:
    value = read_json(paths.local / "instance.json", default={})
    return value if isinstance(value, dict) else {}
