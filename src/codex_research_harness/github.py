from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import load_project_spec
from .models import LabPaths
from .utils import CommandResult, atomic_write_json, atomic_write_text, iso_now, read_json, run_command


class GitHubError(RuntimeError):
    pass


@dataclass
class GitHubContext:
    owner: str
    repo: str
    name_with_owner: str
    repo_url: str
    project_number: int | None = None
    project_id: str | None = None
    project_url: str | None = None


class GitHubClient:
    """Idempotent GitHub Projects control-plane client.

    GitHub CLI owns repository/Project mutations. Saved view layout creation is
    intentionally delegated to the browser Skill because `gh project` does not
    expose a stable view-creation interface.
    """

    def __init__(self, paths: LabPaths, *, dry_run: bool = False) -> None:
        self.paths = paths
        self.dry_run = dry_run
        self.commands: list[list[str]] = []
        self._dry_issue_counter = 0
        self._dry_fields: list[dict[str, Any]] = []
        self._dry_items: list[dict[str, Any]] = []
        self._dry_issues: dict[str, dict[str, Any]] = {}

    def _run(self, args: list[str], *, timeout: float = 30, require_ok: bool = True) -> CommandResult:
        self.commands.append(args)
        if self.dry_run:
            return CommandResult(args, 0, "{}", "", 0.0)
        result = run_command(args, cwd=self.paths.root, timeout=timeout)
        if require_ok and not result.ok:
            raise GitHubError(f"Command failed: {' '.join(args)}\n{result.stderr or result.stdout}")
        return result

    def gh(self, *args: str, timeout: float = 30, require_ok: bool = True) -> CommandResult:
        return self._run(["gh", *args], timeout=timeout, require_ok=require_ok)

    @staticmethod
    def _json(result: CommandResult) -> Any:
        try:
            return json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise GitHubError(f"Expected JSON from {' '.join(result.command)}: {result.stdout}") from exc

    @staticmethod
    def _parse_remote(value: str, fallback_repo: str) -> tuple[str, str]:
        remote = value.strip().removesuffix(".git")
        if remote.startswith("git@") and ":" in remote:
            remote = remote.split(":", 1)[1]
        elif "://" in remote:
            parsed = urlparse(remote)
            remote = parsed.path.lstrip("/")
        parts = [part for part in remote.split("/") if part]
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        return "dry-run-owner", fallback_repo

    def discover(self) -> GitHubContext:
        if self.dry_run:
            self.commands.append(["gh", "repo", "view", "--json", "nameWithOwner,url"])
            remote = run_command(["git", "remote", "get-url", "origin"], cwd=self.paths.root)
            owner, repo = self._parse_remote(remote.stdout if remote.ok else "", self.paths.root.name)
            name_with_owner = f"{owner}/{repo}"
            return GitHubContext(owner, repo, name_with_owner, f"https://github.com/{name_with_owner}")
        value = self._json(self.gh("repo", "view", "--json", "nameWithOwner,url"))
        name_with_owner = value["nameWithOwner"]
        owner, repo = name_with_owner.split("/", 1)
        return GitHubContext(owner, repo, name_with_owner, value["url"])

    def ensure_labels(self, labels: list[dict[str, str]]) -> None:
        for label in labels:
            args = [
                "label",
                "create",
                label["name"],
                "--color",
                label.get("color", "6f42c1").lstrip("#"),
                "--description",
                label.get("description", ""),
                "--force",
            ]
            self.gh(*args)

    def list_projects(self, owner: str) -> list[dict[str, Any]]:
        if self.dry_run:
            self.commands.append(
                ["gh", "project", "list", "--owner", owner, "--format", "json", "--limit", "100"]
            )
            return []
        value = self._json(self.gh("project", "list", "--owner", owner, "--format", "json", "--limit", "100"))
        if isinstance(value, dict):
            return list(value.get("projects", []))
        return list(value)

    def ensure_project(self, context: GitHubContext, title: str) -> GitHubContext:
        existing = next(
            (item for item in self.list_projects(context.owner) if item.get("title") == title), None
        )
        if existing is None:
            if self.dry_run:
                self.commands.append(
                    [
                        "gh",
                        "project",
                        "create",
                        "--owner",
                        context.owner,
                        "--title",
                        title,
                        "--format",
                        "json",
                    ]
                )
                existing = {
                    "number": 1,
                    "id": "PVT_DRY_RUN",
                    "url": f"https://github.com/users/{context.owner}/projects/1",
                    "title": title,
                }
            else:
                existing = self._json(
                    self.gh(
                        "project", "create", "--owner", context.owner, "--title", title, "--format", "json"
                    )
                )
        context.project_number = int(existing.get("number"))
        context.project_id = existing.get("id")
        context.project_url = existing.get("url")
        self.gh(
            "project",
            "link",
            str(context.project_number),
            "--owner",
            context.owner,
            "--repo",
            context.repo,
        )
        return context

    def list_fields(self, context: GitHubContext) -> list[dict[str, Any]]:
        if context.project_number is None:
            raise GitHubError("Project not initialized")
        if self.dry_run:
            self.commands.append(
                [
                    "gh",
                    "project",
                    "field-list",
                    str(context.project_number),
                    "--owner",
                    context.owner,
                    "--format",
                    "json",
                    "--limit",
                    "100",
                ]
            )
            if not self._dry_fields and (self.paths.local / "github.json").exists():
                for index, field in enumerate(load_project_spec(self.paths).get("fields", []), 1):
                    self._dry_fields.append(
                        {
                            "id": f"PVTF_DRY_{index}",
                            "name": field["name"],
                            "dataType": field["type"],
                            "options": [
                                {"id": f"PVTFO_DRY_{index}_{option_index}", "name": option}
                                for option_index, option in enumerate(field.get("options", []), 1)
                            ],
                        }
                    )
            return list(self._dry_fields)
        value = self._json(
            self.gh(
                "project",
                "field-list",
                str(context.project_number),
                "--owner",
                context.owner,
                "--format",
                "json",
                "--limit",
                "100",
            )
        )
        return list(value.get("fields", value if isinstance(value, list) else []))

    def ensure_fields(self, context: GitHubContext, fields: list[dict[str, Any]]) -> None:
        current = {item.get("name"): item for item in self.list_fields(context)}
        for field in fields:
            if field["name"] in current:
                continue
            data_type = field["type"].upper()
            args = [
                "project",
                "field-create",
                str(context.project_number),
                "--owner",
                context.owner,
                "--name",
                field["name"],
                "--data-type",
                data_type,
            ]
            if data_type == "SINGLE_SELECT":
                args.extend(["--single-select-options", ",".join(field.get("options", []))])
            self.gh(*args)
            if self.dry_run:
                index = len(self._dry_fields) + 1
                self._dry_fields.append(
                    {
                        "id": f"PVTF_DRY_{index}",
                        "name": field["name"],
                        "dataType": data_type,
                        "options": [
                            {"id": f"PVTFO_DRY_{index}_{option_index}", "name": option}
                            for option_index, option in enumerate(field.get("options", []), 1)
                        ],
                    }
                )

    def find_issue_by_marker(self, context: GitHubContext, marker: str) -> dict[str, Any] | None:
        if self.dry_run:
            self.commands.append(
                [
                    "gh",
                    "issue",
                    "list",
                    "--repo",
                    context.name_with_owner,
                    "--state",
                    "all",
                    "--search",
                    f'"{marker}" in:body',
                    "--json",
                    "number,title,url,body,state",
                    "--limit",
                    "100",
                ]
            )
            return self._dry_issues.get(marker)
        value = self._json(
            self.gh(
                "issue",
                "list",
                "--repo",
                context.name_with_owner,
                "--state",
                "all",
                "--search",
                f'"{marker}" in:body',
                "--json",
                "number,title,url,body,state",
                "--limit",
                "100",
            )
        )
        for item in value:
            if marker in (item.get("body") or ""):
                return item
        return None

    def ensure_issue(
        self, context: GitHubContext, issue: dict[str, Any], *, update_existing: bool = False
    ) -> dict[str, Any]:
        marker = f"<!-- crh:key={issue['key']} -->"
        existing = self.find_issue_by_marker(context, marker)
        body = marker + "\n\n" + issue.get("body", "")
        labels = issue.get("labels", [])
        if existing:
            if update_existing and (
                existing.get("title") != issue["title"] or (existing.get("body") or "") != body
            ):
                args = [
                    "issue",
                    "edit",
                    str(existing["number"]),
                    "--repo",
                    context.name_with_owner,
                    "--title",
                    issue["title"],
                    "--body",
                    body,
                ]
                if labels:
                    args.extend(["--add-label", ",".join(labels)])
                self.gh(*args)
                existing.update({"title": issue["title"], "body": body})
            return existing
        args = [
            "issue",
            "create",
            "--repo",
            context.name_with_owner,
            "--title",
            issue["title"],
            "--body",
            body,
        ]
        if labels:
            args.extend(["--label", ",".join(labels)])
        if self.dry_run:
            self.commands.append(["gh", *args])
            self._dry_issue_counter += 1
            number = self._dry_issue_counter
            value = {
                "url": f"https://github.com/{context.name_with_owner}/issues/{number}",
                "number": number,
                "title": issue["title"],
                "body": body,
                "state": "OPEN",
            }
            self._dry_issues[marker] = value
            return value
        result = self.gh(*args)
        url = result.stdout.strip().splitlines()[-1]
        number_match = re.search(r"/(\d+)$", url)
        return {
            "url": url,
            "number": int(number_match.group(1)) if number_match else None,
            "title": issue["title"],
            "body": body,
            "state": "OPEN",
        }

    def list_items(self, context: GitHubContext) -> list[dict[str, Any]]:
        if context.project_number is None:
            raise GitHubError("Project not initialized")
        if self.dry_run:
            self.commands.append(
                [
                    "gh",
                    "project",
                    "item-list",
                    str(context.project_number),
                    "--owner",
                    context.owner,
                    "--format",
                    "json",
                    "--limit",
                    "1000",
                ]
            )
            return list(self._dry_items)
        value = self._json(
            self.gh(
                "project",
                "item-list",
                str(context.project_number),
                "--owner",
                context.owner,
                "--format",
                "json",
                "--limit",
                "1000",
            )
        )
        return list(value.get("items", value if isinstance(value, list) else []))

    @staticmethod
    def _item_content_url(item: dict[str, Any]) -> str | None:
        content = item.get("content")
        if isinstance(content, dict):
            return content.get("url")
        return item.get("url")

    def ensure_item(self, context: GitHubContext, url: str) -> dict[str, Any]:
        existing = next(
            (item for item in self.list_items(context) if self._item_content_url(item) == url), None
        )
        if existing:
            return existing
        if self.dry_run:
            self.commands.append(
                [
                    "gh",
                    "project",
                    "item-add",
                    str(context.project_number),
                    "--owner",
                    context.owner,
                    "--url",
                    url,
                    "--format",
                    "json",
                ]
            )
            import hashlib

            item = {
                "id": f"PVTI_DRY_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:12]}",
                "content": {"url": url},
            }
            self._dry_items.append(item)
            return item
        return self._json(
            self.gh(
                "project",
                "item-add",
                str(context.project_number),
                "--owner",
                context.owner,
                "--url",
                url,
                "--format",
                "json",
            )
        )

    def _load_context_from_state(self) -> GitHubContext:
        state = read_json(self.paths.local / "github.json", default={})
        if not isinstance(state, dict) or not state.get("project_number"):
            raise GitHubError("GitHub Project is not configured; run `researchctl github setup` first")
        repository = str(state["repository"])
        owner, repo = repository.split("/", 1)
        return GitHubContext(
            owner=owner,
            repo=repo,
            name_with_owner=repository,
            repo_url=str(state.get("repository_url") or f"https://github.com/{repository}"),
            project_number=int(state["project_number"]),
            project_id=state.get("project_id"),
            project_url=state.get("project_url"),
        )

    @staticmethod
    def _option_id(field: dict[str, Any], label: str) -> str | None:
        for option in field.get("options", []) or []:
            if option.get("name") == label:
                return option.get("id")
        return None

    def edit_item_fields(self, context: GitHubContext, item_id: str, values: dict[str, Any]) -> None:
        if not context.project_id:
            raise GitHubError("Project ID is unavailable")
        fields = {item.get("name"): item for item in self.list_fields(context)}
        for name, raw in values.items():
            if raw is None or name not in fields:
                continue
            field = fields[name]
            field_id = field.get("id")
            if not field_id:
                continue
            args = [
                "project",
                "item-edit",
                "--id",
                item_id,
                "--project-id",
                context.project_id,
                "--field-id",
                field_id,
            ]
            spec_types = {
                item["name"]: item["type"].upper() for item in load_project_spec(self.paths).get("fields", [])
            }
            data_type = spec_types.get(name, str(field.get("dataType") or field.get("type") or "").upper())
            if data_type == "SINGLE_SELECT":
                option_id = self._option_id(field, str(raw))
                if not option_id:
                    continue
                args.extend(["--single-select-option-id", option_id])
            elif data_type == "NUMBER":
                args.extend(["--number", str(float(raw))])
            elif data_type == "DATE":
                args.extend(["--date", str(raw)[:10]])
            else:
                args.extend(["--text", str(raw)])
            self.gh(*args)

    def setup_project(self) -> dict[str, Any]:
        spec = load_project_spec(self.paths)
        context = self.discover()
        title = spec["project"]["title_template"].replace("{{repository}}", context.repo)
        self.ensure_labels(spec.get("labels", []))
        context = self.ensure_project(context, title)
        self.ensure_fields(context, spec.get("fields", []))
        issues = []
        for issue_spec in spec.get("seed_issues", []):
            issue = self.ensure_issue(context, issue_spec, update_existing=True)
            if issue.get("url"):
                self.ensure_item(context, issue["url"])
            issues.append(issue)
        state = {
            "schema_version": 1,
            "repository": context.name_with_owner,
            "repository_url": context.repo_url,
            "project_title": title,
            "project_number": context.project_number,
            "project_id": context.project_id,
            "project_url": context.project_url,
            "seed_issues": issues,
            "views": spec.get("views", []),
            "views_status": "requires_browser_configuration",
            "configured_at": iso_now(),
            "dry_run": self.dry_run,
            "commands": self.commands if self.dry_run else None,
        }
        self.paths.ensure_runtime()
        atomic_write_json(self.paths.local / "github.json", state)
        atomic_write_text(self.paths.setup / "GITHUB_PROJECT.md", render_project_summary(state))
        return state

    def sync_campaign(self, campaign_id: str) -> dict[str, Any]:
        context = self._load_context_from_state()
        directory = self.paths.campaigns / campaign_id
        contract = read_json(directory / "CONTRACT.json", default={})
        state = read_json(directory / "STATE.json", default={})
        if not contract or not state:
            raise FileNotFoundError(f"Unknown or incomplete campaign {campaign_id}")
        issue_spec = {
            "key": f"CAMPAIGN:{campaign_id}",
            "title": f"[{campaign_id}] {contract.get('title', 'Research Campaign')}",
            "labels": ["research:campaign", "agent:executor"],
            "body": render_campaign_issue(contract, state),
        }
        issue = self.ensure_issue(context, issue_spec, update_existing=True)
        item = self.ensure_item(context, issue["url"])
        item_id = item.get("id")
        if item_id:
            self.edit_item_fields(context, item_id, campaign_project_values(contract, state))
        sync_state = {
            "campaign_id": campaign_id,
            "issue": issue,
            "project_item_id": item_id,
            "synced_at": iso_now(),
            "dry_run": self.dry_run,
        }
        atomic_write_json(directory / "GITHUB_SYNC.json", sync_state)
        return sync_state

    def sync_all_campaigns(self) -> list[dict[str, Any]]:
        return [
            self.sync_campaign(path.name)
            for path in sorted(self.paths.campaigns.glob("C-*"))
            if path.is_dir()
        ]


def _project_status(status: str) -> str:
    return {
        "draft": "Planning",
        "ready": "Ready",
        "executing": "Executing",
        "waiting": "Waiting",
        "validating": "Validating",
        "reporting": "Reporting",
        "replanning": "Replanning",
        "completed": "Done",
        "stopped": "Stopped",
    }.get(status, "Planning")


def _project_phase(phase: str) -> str:
    return {
        "contract": "Contract",
        "context_pack": "Contract",
        "smoke": "Smoke",
        "quick": "Quick",
        "full_cv": "Full CV",
        "confirm": "Confirm",
        "synthesis": "Synthesis",
        "handoff": "Handoff",
    }.get(phase, "Contract")


def _project_health(health: str) -> str:
    return {"on_track": "On track", "at_risk": "At risk", "blocked": "Blocked"}.get(health, "On track")


def _project_signal(signal: str) -> str:
    return {
        "unknown": "Unknown",
        "weak": "Weak",
        "promising": "Promising",
        "competitive": "Competitive",
        "breakthrough": "Breakthrough",
    }.get(signal, "Unknown")


def _project_outcome(outcome: str | None) -> str | None:
    return (
        {
            "success": "Success",
            "promising": "Promising",
            "rejected_with_evidence": "Rejected",
            "surprise": "Surprise",
            "strategy_conflict": "Surprise",
            "blocked": "Blocked",
            "budget_exhausted": "Budget exhausted",
            "invalid": "Invalid",
        }.get(outcome)
        if outcome
        else None
    )


def campaign_project_values(contract: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    resources = state.get("resources", {})
    budget = contract.get("budget", {})
    forecast = state.get("forecast", {})
    owner = contract.get("owner", {})
    next_actions = state.get("next_actions", [])
    gpu_planned = float(budget.get("gpu_hours", 0) or 0)
    resource = "GPU0" if gpu_planned > 0 else "CPU"
    accountable = "Planner" if state.get("status") == "draft" else "Executor"
    return {
        "Type": "Campaign",
        "Status": _project_status(str(state.get("status", "draft"))),
        "Phase": _project_phase(str(state.get("phase", "contract"))),
        "Health": _project_health(str(state.get("health", "on_track"))),
        "Accountable Role": accountable,
        "Active Runtime": "/".join(
            str(owner.get(key, "")) for key in ("runtime", "model", "effort") if owner.get(key)
        ),
        "Current Action": state.get("current_action", ""),
        "Next Action": next_actions[0] if next_actions else "",
        "Forecast Date": forecast.get("finish_high"),
        "ETA Window": (
            f"{forecast.get('finish_low')} – {forecast.get('finish_high')}"
            if forecast.get("finish_low") or forecast.get("finish_high")
            else ""
        ),
        "Resource": resource,
        "GPU Planned h": gpu_planned,
        "GPU Actual h": float(resources.get("gpu_hours_used", 0) or 0),
        "Research Signal": _project_signal(str(state.get("research_signal", "unknown"))),
        "Attention": (
            "External action"
            if state.get("health") == "blocked"
            else "Read"
            if state.get("health") == "at_risk"
            else "None"
        ),
        "Outcome": _project_outcome(state.get("outcome")),
    }


def render_campaign_issue(contract: dict[str, Any], state: dict[str, Any]) -> str:
    progress = state.get("progress", {})
    resources = state.get("resources", {})
    budget = contract.get("budget", {})
    next_actions = "\n".join(f"- {item}" for item in state.get("next_actions", [])) or "- None recorded"
    success = "\n".join(f"- {item}" for item in contract.get("success_conditions", []))
    withdrawal = "\n".join(f"- {item}" for item in contract.get("withdrawal_conditions", []))
    return f"""## Human research cockpit

- **Research signal:** {state.get("research_signal", "unknown")}
- **Status / phase:** {state.get("status", "unknown")} / {state.get("phase", "unknown")}
- **Current action:** {state.get("current_action", "")}
- **Milestones:** {progress.get("completed_milestones", 0)} / {progress.get("total_milestones", 0)}
- **Wall time:** {resources.get("wall_hours_used", 0)} / {budget.get("wall_hours", 0)} h
- **GPU time:** {resources.get("gpu_hours_used", 0)} / {budget.get("gpu_hours", 0)} h
- **Cost:** JPY {resources.get("cost_jpy", 0)} / {budget.get("paid_compute_jpy", 0)}
- **Budget gate:** {state.get("budget_status", "unknown")}

## Goal

{contract.get("goal", "")}

## Why now

{contract.get("why_now", "")}

## Success conditions

{success}

## Withdrawal conditions

{withdrawal}

## Next actions

{next_actions}

## Evidence and implementation

- Contract: `research/campaigns/{contract.get("campaign_id")}/CONTRACT.json`
- Current state: `research/campaigns/{contract.get("campaign_id")}/STATE.md`
- Handoff: `research/campaigns/{contract.get("campaign_id")}/HANDOFF.md`

This body is generated by `researchctl github sync`; do not use the Issue body as
the research state of record.
"""


def render_project_summary(state: dict[str, Any]) -> str:
    views = "\n".join(f"- {item['name']}: {item.get('purpose', '')}" for item in state.get("views", []))
    return f"""# GitHub research control plane

- Repository: `{state.get("repository")}`
- Project: [{state.get("project_title")}]({state.get("project_url")})
- Project number: `{state.get("project_number")}`
- View configuration: **{state.get("views_status")}**

## Required views

{views}

Fields, labels, seed issues, repository linking, and Campaign synchronization are
configured with GitHub CLI. View layouts and saved filters are completed by the
`github-project-setup` browser skill because GitHub CLI does not expose a stable
view-creation command. The skill is idempotent and verifies each view after
creation.
"""


def write_project_plan(paths: LabPaths) -> Path:
    spec = load_project_spec(paths)
    rows = []
    for field in spec.get("fields", []):
        options = ", ".join(field.get("options", []))
        rows.append(f"- **{field['name']}** — `{field['type']}`{f': {options}' if options else ''}")
    views = []
    for view in spec.get("views", []):
        views.append(
            f"### {view['name']}\n\n- Layout: `{view.get('layout', 'table')}`\n"
            f"- Filter: `{view.get('filter', '')}`\n- Purpose: {view.get('purpose', '')}\n"
        )
    output = paths.runtime / "github-project-plan.md"
    atomic_write_text(
        output,
        "# GitHub Project setup plan\n\n## Fields\n\n"
        + "\n".join(rows)
        + "\n\n## Views\n\n"
        + "\n".join(views),
    )
    return output
