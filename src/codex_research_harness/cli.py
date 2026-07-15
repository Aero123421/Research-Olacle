from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .bootstrap import initialize_repository
from .brief import generate_human_brief
from .campaign import (
    activate_campaign,
    complete_campaign,
    create_campaign,
    finalize_campaign_contract,
    list_campaign_ids,
    update_campaign_state,
    validate_contract_file,
)
from .consultation import (
    choose_preferred_model,
    configure_browser,
    get_consultation_route,
    load_chatgpt_state,
    mark_chatgpt_degraded,
    prepare_consultation,
    record_chatgpt_project,
    record_consultation_response,
    record_consultation_synthesis,
    suggest_chatgpt_project_name,
    verify_chatgpt_project,
)
from .context import build_executor_context, build_planner_context, check_context_sizes
from .doctor import doctor_exit_code, run_doctor
from .eda import profile_dataset
from .experiments import read_experiments, register_experiment
from .github import GitHubClient, write_project_plan
from .jobs import (
    finish_job,
    gpu_queue,
    heartbeat_job,
    list_jobs,
    register_job,
    start_job,
    sync_campaign_resources,
)
from .loop import inspect_research_loop, render_loop_instruction, write_loop_state
from .models import LabPaths
from .plans import create_research_plan, link_campaign, list_plan_ids, update_research_plan
from .repository import adopt_repository
from .schema import ValidationError
from .selftest import run_self_test
from .utils import find_repo_root, read_json
from .visualize import generate_all


def _paths(args: argparse.Namespace) -> LabPaths:
    root = Path(args.root).resolve() if getattr(args, "root", None) else find_repo_root()
    paths = LabPaths(root)
    paths.ensure_runtime()
    return paths


def _json_arg(value: str) -> dict[str, Any]:
    candidate = Path(value)
    if candidate.exists():
        raw = read_json(candidate)
    else:
        raw = json.loads(value)
    if not isinstance(raw, dict):
        raise ValueError("Expected a JSON object")
    return raw


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="researchctl",
        description="Control plane CLI for Codex Research Harness",
    )
    parser.add_argument("--root", help="Repository root; auto-detected by default")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize local research-lab state idempotently")
    init.add_argument("--answers", help="JSON file with setup answers")
    init.add_argument("--force", action="store_true")

    doctor = sub.add_parser("doctor", help="Probe repository, agents, services, and compute")
    doctor.add_argument("--profile", choices=["quick", "core", "agents", "kaggle", "full"], default="full")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--strict", action="store_true")

    repo = sub.add_parser("repo", help="Manage repository lifecycle")
    repo_sub = repo.add_subparsers(dest="repo_command", required=True)
    adopt = repo_sub.add_parser("adopt", help="Turn this template clone into a new GitHub repository")
    adopt.add_argument("repository", help="OWNER/NAME")
    adopt.add_argument("--visibility", choices=["private", "public", "internal"], default="private")
    adopt.add_argument("--no-push", action="store_true")
    adopt.add_argument("--dry-run", action="store_true")

    github = sub.add_parser("github", help="Create and synchronize the GitHub control plane")
    github_sub = github.add_subparsers(dest="github_command", required=True)
    github_sub.add_parser("plan", help="Render the project setup specification")
    setup = github_sub.add_parser("setup", help="Create project, fields, labels, and seed issues")
    setup.add_argument("--dry-run", action="store_true")
    sync = github_sub.add_parser(
        "sync", help="Synchronize Campaign state to GitHub Issues and Project fields"
    )
    sync.add_argument("campaign_id", nargs="?", help="Campaign ID; omit with --all")
    sync.add_argument("--all", action="store_true", help="Synchronize every Campaign")
    sync.add_argument("--dry-run", action="store_true")

    plan = sub.add_parser("plan", help="Manage durable ResearchPlan state")
    plan_sub = plan.add_subparsers(dest="plan_command", required=True)
    plan_create = plan_sub.add_parser("create")
    intent_group = plan_create.add_mutually_exclusive_group(required=True)
    intent_group.add_argument("--intent")
    intent_group.add_argument("--intent-file")
    plan_create.add_argument("--target")
    plan_create.add_argument("--deadline")
    plan_create.add_argument("--id", dest="plan_id")
    plan_checkpoint = plan_sub.add_parser("checkpoint")
    plan_checkpoint.add_argument("plan_id")
    plan_checkpoint.add_argument("--patch", required=True)
    plan_link = plan_sub.add_parser("link-campaign")
    plan_link.add_argument("plan_id")
    plan_link.add_argument("campaign_id")
    plan_sub.add_parser("list")

    context = sub.add_parser("context", help="Build bounded Planner/Executor context packs")
    context_sub = context.add_subparsers(dest="context_command", required=True)
    context_sub.add_parser("planner")
    executor = context_sub.add_parser("executor")
    executor.add_argument("campaign_id")
    context_sub.add_parser("check")

    campaign = sub.add_parser("campaign", help="Manage autonomous research campaigns")
    campaign_sub = campaign.add_subparsers(dest="campaign_command", required=True)
    create = campaign_sub.add_parser("create")
    create.add_argument("--title", required=True)
    create.add_argument("--goal", required=True)
    create.add_argument("--id", dest="campaign_id")
    create.add_argument("--contract", help="Full contract JSON file")
    validate = campaign_sub.add_parser("validate")
    validate.add_argument("campaign_id")
    finalize = campaign_sub.add_parser("finalize", help="Mark a fully specified Planner contract ready")
    finalize.add_argument("campaign_id")
    activate = campaign_sub.add_parser("activate")
    activate.add_argument("campaign_id")
    checkpoint = campaign_sub.add_parser("checkpoint")
    checkpoint.add_argument("campaign_id")
    checkpoint.add_argument("--patch", required=True, help="JSON object or file")
    complete = campaign_sub.add_parser("complete")
    complete.add_argument("campaign_id")
    complete.add_argument("--handoff", required=True, help="Handoff JSON file")
    campaign_sub.add_parser("list")

    chatgpt = sub.add_parser("chatgpt", help="Prepare and track browser-based ChatGPT Project consultations")
    chat_sub = chatgpt.add_subparsers(dest="chatgpt_command", required=True)
    browser = chat_sub.add_parser("browser")
    browser.add_argument("mode", choices=["built_in", "chrome"])
    browser.add_argument("--chrome-profile")
    chat_sub.add_parser("project-name", help="Suggest a stable ChatGPT Project title")
    choose = chat_sub.add_parser("choose-model", help="Select the first exact configured Pro label")
    choose.add_argument("--available", action="append", default=[], required=True)
    choose.add_argument("--preference", action="append", default=[])
    project = chat_sub.add_parser("record-project")
    project.add_argument("--browser", choices=["built_in", "chrome"], required=True)
    project.add_argument("--name", required=True)
    project.add_argument("--url", required=True)
    project.add_argument("--model-label", required=True)
    project.add_argument("--preference", action="append", default=[])
    project.add_argument("--available-label", action="append", default=[])
    verify = chat_sub.add_parser("verify-project")
    verify.add_argument("--model-label", required=True)
    verify.add_argument("--url")
    verify.add_argument("--name")
    prepare = chat_sub.add_parser("prepare")
    prepare.add_argument("--question", required=True)
    prepare.add_argument("--purpose", required=True)
    prepare.add_argument("--requester", required=True)
    prepare.add_argument("--context", action="append", default=[])
    prepare.add_argument("--follow-up-to")
    record = chat_sub.add_parser("record-response")
    record.add_argument("question_id")
    record.add_argument("--url", required=True)
    record.add_argument("--response-file", required=True)
    record.add_argument("--model-label", required=True)
    synthesis = chat_sub.add_parser(
        "record-synthesis", help="Save the bounded advisor result eligible for Planner context"
    )
    synthesis.add_argument("question_id")
    synthesis.add_argument("--file", required=True)
    route = chat_sub.add_parser("route", help="Read a locally saved conversation route")
    route.add_argument("question_id")
    degraded = chat_sub.add_parser(
        "degrade", help="Mark browser consultation unavailable without stopping research"
    )
    degraded.add_argument("--reason", required=True)
    chat_sub.add_parser("status")

    loop = sub.add_parser("loop", help="Derive the next Planner/Executor transition from durable state")
    loop_sub = loop.add_subparsers(dest="loop_command", required=True)
    loop_sub.add_parser("status", help="Print the next transition as JSON")
    loop_sub.add_parser("instruction", help="Render the next Codex App Director instruction")
    loop_sub.add_parser("checkpoint", help="Persist the current loop decision to local runtime state")

    job = sub.add_parser("job", help="Track durable compute jobs and GPU queue state")
    job_sub = job.add_subparsers(dest="job_command", required=True)
    job_register = job_sub.add_parser("register", help="Register a queued compute job without executing it")
    job_register.add_argument("--campaign", required=True)
    job_register.add_argument("--name", required=True)
    job_register.add_argument("--resource", required=True)
    job_register.add_argument("--planned-hours", type=float, required=True)
    job_register.add_argument("--backend", default="local_windows")
    job_register.add_argument("--command-summary")
    job_register.add_argument("--after")
    job_register.add_argument("--id", dest="job_id")
    job_start = job_sub.add_parser("start")
    job_start.add_argument("job_id")
    job_heartbeat = job_sub.add_parser("heartbeat")
    job_heartbeat.add_argument("job_id")
    job_heartbeat.add_argument("--progress")
    job_heartbeat.add_argument("--wall-hours", type=float)
    job_heartbeat.add_argument("--gpu-hours", type=float)
    job_finish = job_sub.add_parser("finish")
    job_finish.add_argument("job_id")
    job_finish.add_argument("--status", choices=["completed", "failed", "cancelled"], default="completed")
    job_finish.add_argument("--exit-code", type=int)
    job_finish.add_argument("--failure-summary")
    job_finish.add_argument("--wall-hours", type=float)
    job_finish.add_argument("--gpu-hours", type=float)
    job_list = job_sub.add_parser("list")
    job_list.add_argument("--campaign")
    job_list.add_argument("--status")
    job_list.add_argument("--resource")
    job_sub.add_parser("gpu-queue")
    job_sync = job_sub.add_parser("sync-campaign")
    job_sync.add_argument("campaign_id")

    experiment = sub.add_parser("experiment", help="Register reproducible experiment evidence")
    exp_sub = experiment.add_subparsers(dest="experiment_command", required=True)
    exp_reg = exp_sub.add_parser("register")
    exp_reg.add_argument("--file", required=True)
    exp_sub.add_parser("list")

    eda = sub.add_parser("eda", help="Generate deterministic baseline data inventories")
    eda_sub = eda.add_subparsers(dest="eda_command", required=True)
    profile = eda_sub.add_parser("profile")
    profile.add_argument("path")
    profile.add_argument("--output", default="research/plans/evidence")
    profile.add_argument("--max-rows", type=int, default=100_000)

    sub.add_parser("brief", help="Generate a low-cognitive-load human status brief")
    sub.add_parser("visualize", help="Generate deterministic research/GPU visualizations")
    sub.add_parser("self-test", help="Run non-network structural checks")
    return parser


def command_init(args: argparse.Namespace) -> int:
    paths = _paths(args)
    answers = read_json(Path(args.answers)) if args.answers else None
    _print_json(initialize_repository(paths, answers=answers, force=args.force))
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    report = run_doctor(_paths(args), profile=args.profile)
    if args.json:
        _print_json(report.to_dict())
    else:
        for result in report.results:
            print(f"{result.status.upper():4} {result.name:24} {result.summary}")
        print(f"\nReadiness report: {_paths(args).setup / 'READINESS.md'}")
    return doctor_exit_code(report, strict=args.strict)


def command_repo(args: argparse.Namespace) -> int:
    if args.repo_command == "adopt":
        _print_json(
            adopt_repository(
                _paths(args),
                name_with_owner=args.repository,
                visibility=args.visibility,
                dry_run=args.dry_run,
                push=not args.no_push,
            )
        )
    return 0


def command_github(args: argparse.Namespace) -> int:
    paths = _paths(args)
    if args.github_command == "plan":
        print(write_project_plan(paths))
    elif args.github_command == "setup":
        _print_json(GitHubClient(paths, dry_run=args.dry_run).setup_project())
    elif args.github_command == "sync":
        client = GitHubClient(paths, dry_run=args.dry_run)
        if args.all:
            _print_json({"campaigns": client.sync_all_campaigns()})
        elif args.campaign_id:
            _print_json(client.sync_campaign(args.campaign_id))
        else:
            raise ValueError("Provide a campaign ID or --all")
    return 0


def command_plan(args: argparse.Namespace) -> int:
    paths = _paths(args)
    if args.plan_command == "create":
        intent = (
            args.intent if args.intent is not None else Path(args.intent_file).read_text(encoding="utf-8")
        )
        print(
            create_research_plan(
                paths,
                user_intent=intent,
                target=args.target,
                deadline=args.deadline,
                plan_id=args.plan_id,
            )
        )
    elif args.plan_command == "checkpoint":
        _print_json(update_research_plan(paths, args.plan_id, _json_arg(args.patch)))
    elif args.plan_command == "link-campaign":
        _print_json(link_campaign(paths, args.plan_id, args.campaign_id))
    else:
        _print_json({"plans": list_plan_ids(paths)})
    return 0


def command_context(args: argparse.Namespace) -> int:
    paths = _paths(args)
    if args.context_command == "planner":
        result = build_planner_context(paths)
        _print_json(result.__dict__ | {"output": str(result.output)})
    elif args.context_command == "executor":
        result = build_executor_context(paths, args.campaign_id)
        _print_json(result.__dict__ | {"output": str(result.output)})
    else:
        warnings = check_context_sizes(paths)
        _print_json({"warnings": warnings, "ok": not warnings})
        return 1 if warnings else 0
    return 0


def command_campaign(args: argparse.Namespace) -> int:
    paths = _paths(args)
    if args.campaign_command == "create":
        contract = read_json(Path(args.contract)) if args.contract else None
        print(
            create_campaign(
                paths, title=args.title, goal=args.goal, contract=contract, campaign_id=args.campaign_id
            )
        )
    elif args.campaign_command == "validate":
        issues = validate_contract_file(paths.campaigns / args.campaign_id / "CONTRACT.json")
        _print_json({"campaign_id": args.campaign_id, "valid": not issues, "issues": issues})
        return 1 if issues else 0
    elif args.campaign_command == "finalize":
        _print_json(finalize_campaign_contract(paths, args.campaign_id))
    elif args.campaign_command == "activate":
        _print_json(activate_campaign(paths, args.campaign_id))
    elif args.campaign_command == "checkpoint":
        _print_json(update_campaign_state(paths, args.campaign_id, _json_arg(args.patch)))
    elif args.campaign_command == "complete":
        handoff = read_json(Path(args.handoff))
        _print_json(complete_campaign(paths, args.campaign_id, handoff))
    else:
        _print_json({"campaigns": list_campaign_ids(paths)})
    return 0


def command_chatgpt(args: argparse.Namespace) -> int:
    paths = _paths(args)
    if args.chatgpt_command == "browser":
        _print_json(configure_browser(paths, mode=args.mode, chrome_profile=args.chrome_profile))
    elif args.chatgpt_command == "project-name":
        _print_json({"project_name": suggest_chatgpt_project_name(paths)})
    elif args.chatgpt_command == "choose-model":
        _print_json({"selected_model_label": choose_preferred_model(args.available, args.preference or None)})
    elif args.chatgpt_command == "record-project":
        _print_json(
            record_chatgpt_project(
                paths,
                browser_mode=args.browser,
                project_name=args.name,
                project_url=args.url,
                selected_model_label=args.model_label,
                model_preference=args.preference or None,
                available_model_labels=args.available_label or None,
            )
        )
    elif args.chatgpt_command == "verify-project":
        _print_json(
            verify_chatgpt_project(
                paths,
                actual_model_label=args.model_label,
                project_url=args.url,
                project_name=args.name,
            )
        )
    elif args.chatgpt_command == "prepare":
        print(
            prepare_consultation(
                paths,
                question=args.question,
                purpose=args.purpose,
                requester_role=args.requester,
                context_files=args.context,
                follow_up_to=args.follow_up_to,
            )
        )
    elif args.chatgpt_command == "record-response":
        response = Path(args.response_file).read_text(encoding="utf-8")
        _print_json(
            record_consultation_response(
                paths,
                question_id=args.question_id,
                conversation_url=args.url,
                response_text=response,
                actual_model_label=args.model_label,
            )
        )
    elif args.chatgpt_command == "record-synthesis":
        _print_json(
            record_consultation_synthesis(
                paths,
                question_id=args.question_id,
                synthesis_text=Path(args.file).read_text(encoding="utf-8"),
            )
        )
    elif args.chatgpt_command == "route":
        _print_json(get_consultation_route(paths, args.question_id))
    elif args.chatgpt_command == "degrade":
        _print_json(mark_chatgpt_degraded(paths, args.reason))
    else:
        _print_json(load_chatgpt_state(paths))
    return 0


def command_loop(args: argparse.Namespace) -> int:
    paths = _paths(args)
    if args.loop_command == "status":
        _print_json(inspect_research_loop(paths).to_dict())
    elif args.loop_command == "instruction":
        print(render_loop_instruction(inspect_research_loop(paths)))
    else:
        _print_json(write_loop_state(paths))
    return 0


def command_job(args: argparse.Namespace) -> int:
    paths = _paths(args)
    if args.job_command == "register":
        _print_json(
            register_job(
                paths,
                campaign_id=args.campaign,
                name=args.name,
                resource=args.resource,
                planned_hours=args.planned_hours,
                backend=args.backend,
                command_summary=args.command_summary,
                queue_after=args.after,
                job_id=args.job_id,
            )
        )
    elif args.job_command == "start":
        _print_json(start_job(paths, args.job_id))
    elif args.job_command == "heartbeat":
        _print_json(
            heartbeat_job(
                paths,
                args.job_id,
                progress=args.progress,
                actual_wall_hours=args.wall_hours,
                actual_gpu_hours=args.gpu_hours,
            )
        )
    elif args.job_command == "finish":
        _print_json(
            finish_job(
                paths,
                args.job_id,
                status=args.status,
                exit_code=args.exit_code,
                failure_summary=args.failure_summary,
                actual_wall_hours=args.wall_hours,
                actual_gpu_hours=args.gpu_hours,
            )
        )
    elif args.job_command == "list":
        _print_json(
            {
                "jobs": list_jobs(
                    paths,
                    campaign_id=args.campaign,
                    status=args.status,
                    resource=args.resource,
                )
            }
        )
    elif args.job_command == "gpu-queue":
        _print_json({"jobs": gpu_queue(paths)})
    else:
        _print_json(sync_campaign_resources(paths, args.campaign_id))
    return 0


def command_experiment(args: argparse.Namespace) -> int:
    paths = _paths(args)
    if args.experiment_command == "register":
        _print_json(register_experiment(paths, read_json(Path(args.file))))
    else:
        _print_json({"experiments": read_experiments(paths)})
    return 0


def command_eda(args: argparse.Namespace) -> int:
    paths = _paths(args)
    source = Path(args.path).resolve()
    output = paths.root / args.output
    json_path, md_path = profile_dataset(source, output_dir=output, max_rows=args.max_rows)
    _print_json({"json": str(json_path), "markdown": str(md_path)})
    return 0


def command_self_test(args: argparse.Namespace) -> int:
    result = run_self_test(_paths(args))
    _print_json(result)
    return 0 if result["ok"] else 1


def dispatch(args: argparse.Namespace) -> int:
    handlers = {
        "init": command_init,
        "doctor": command_doctor,
        "repo": command_repo,
        "github": command_github,
        "plan": command_plan,
        "context": command_context,
        "campaign": command_campaign,
        "chatgpt": command_chatgpt,
        "loop": command_loop,
        "job": command_job,
        "experiment": command_experiment,
        "eda": command_eda,
        "brief": lambda value: (print(generate_human_brief(_paths(value))) or 0),
        "visualize": lambda value: (
            _print_json({"generated": [str(path) for path in generate_all(_paths(value))]}) or 0
        ),
        "self-test": command_self_test,
    }
    return handlers[args.command](args)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch(args)
    except (ValidationError, ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("cancelled", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
