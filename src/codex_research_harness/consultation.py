from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .locking import lab_lock
from .models import LabPaths
from .utils import atomic_write_json, atomic_write_text, iso_now, read_json, run_command, safe_relpath

VALID_BROWSER_MODES = {"built_in", "chrome"}
VALID_STATUS = {"unconfigured", "needs_login", "needs_verification", "ready", "degraded"}
DEFAULT_MODEL_PREFERENCE = ["Pro"]


def _is_chatgpt_url(value: str) -> bool:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (hostname == "chatgpt.com" or hostname.endswith(".chatgpt.com"))


def configure_browser(paths: LabPaths, *, mode: str, chrome_profile: str | None = None) -> dict[str, Any]:
    if mode not in VALID_BROWSER_MODES:
        raise ValueError(f"mode must be one of {sorted(VALID_BROWSER_MODES)}")
    if mode == "chrome" and chrome_profile is not None and not chrome_profile.strip():
        raise ValueError("chrome_profile cannot be blank")
    paths.ensure_runtime()
    lines = ["[browser]", f'mode = "{mode}"']
    if chrome_profile:
        escaped = chrome_profile.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'chrome_profile = "{escaped}"')
    lines.extend(
        [
            "dedicated_profile_recommended = true",
            "max_parallel_tasks_in_same_browser = 1",
            "critical_action_retry_limit = 2",
        ]
    )
    atomic_write_text(paths.local / "browser.toml", "\n".join(lines) + "\n")
    return {"mode": mode, "chrome_profile": chrome_profile}


def load_chatgpt_state(paths: LabPaths) -> dict[str, Any]:
    value = read_json(paths.local / "chatgpt.json", default={})
    return value if isinstance(value, dict) else {}


def save_chatgpt_state(paths: LabPaths, value: dict[str, Any]) -> None:
    paths.ensure_runtime()
    atomic_write_json(paths.local / "chatgpt.json", value)


def _load_conversation_routes(paths: LabPaths) -> dict[str, Any]:
    value = read_json(paths.local / "chatgpt-conversations.json", default={})
    return value if isinstance(value, dict) else {}


def _save_conversation_routes(paths: LabPaths, value: dict[str, Any]) -> None:
    paths.ensure_runtime()
    atomic_write_json(paths.local / "chatgpt-conversations.json", value)


def suggest_chatgpt_project_name(paths: LabPaths) -> str:
    """Return a stable, human-readable project name for this repository."""

    remote = run_command(["git", "remote", "get-url", "origin"], cwd=paths.root)
    identity = remote.stdout.strip() if remote.ok and remote.stdout.strip() else str(paths.root.resolve())
    normalized = re.sub(r"(?:https?://|ssh://|git@)", "", identity)
    normalized = normalized.removesuffix(".git").replace(":", "/")
    name = normalized.split("/")[-2:] if "/" in normalized else [paths.root.name]
    readable = "/".join(part for part in name if part) or paths.root.name
    fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8]
    return f"CRH • {readable} • {fingerprint}"


def choose_preferred_model(available_labels: list[str], preference: list[str] | None = None) -> str:
    """Choose an exact model label without fuzzy or silent fallback."""

    cleaned = [item.strip() for item in available_labels if isinstance(item, str) and item.strip()]
    preferred = preference or DEFAULT_MODEL_PREFERENCE
    for label in preferred:
        if label in cleaned:
            return label
    raise ValueError(
        "No configured Pro label is available. Visible labels: " + (", ".join(cleaned) if cleaned else "none")
    )


def record_chatgpt_project(
    paths: LabPaths,
    *,
    browser_mode: str,
    project_name: str,
    project_url: str,
    selected_model_label: str,
    model_preference: list[str] | None = None,
    available_model_labels: list[str] | None = None,
    status: str = "needs_verification",
) -> dict[str, Any]:
    if browser_mode not in VALID_BROWSER_MODES:
        raise ValueError("Invalid browser mode")
    if status not in VALID_STATUS:
        raise ValueError("Invalid ChatGPT integration status")
    if not project_name.strip():
        raise ValueError("project_name must not be blank")
    if not _is_chatgpt_url(project_url):
        raise ValueError("project_url must be an https://chatgpt.com URL")
    preference = model_preference or DEFAULT_MODEL_PREFERENCE
    if available_model_labels is not None:
        chosen = choose_preferred_model(available_model_labels, preference)
        if chosen != selected_model_label:
            raise ValueError(f"Preference policy selects {chosen!r}, not {selected_model_label!r}")
    elif selected_model_label not in preference:
        raise ValueError(
            f"Selected model label {selected_model_label!r} is not in the exact preference list {preference!r}"
        )
    state = {
        "schema_version": 1,
        "browser_mode": browser_mode,
        "project_name": project_name.strip(),
        "project_url": project_url,
        "selected_model_label": selected_model_label,
        "model_preference": preference,
        "available_model_labels_at_setup": available_model_labels or [],
        "allow_silent_fallback": False,
        "project_only_memory_requested": True,
        "status": status,
        "created_at": iso_now(),
        "last_verified_at": None,
    }
    save_chatgpt_state(paths, state)
    write_chatgpt_summary(paths, state)
    return state


def verify_chatgpt_project(
    paths: LabPaths,
    *,
    actual_model_label: str,
    project_url: str | None = None,
    project_name: str | None = None,
) -> dict[str, Any]:
    state = load_chatgpt_state(paths)
    if not state:
        raise FileNotFoundError("ChatGPT project is not configured")
    if project_url and project_url != state.get("project_url"):
        raise ValueError("Verified URL does not match the saved ChatGPT project URL")
    if project_name and project_name.strip() != state.get("project_name"):
        raise ValueError("Verified project name does not match the saved ChatGPT project name")
    expected = state.get("selected_model_label")
    if actual_model_label != expected:
        state["status"] = "degraded"
        state["last_verification_error"] = f"Expected model label {expected!r}, saw {actual_model_label!r}"
        save_chatgpt_state(paths, state)
        write_chatgpt_summary(paths, state)
        raise ValueError(state["last_verification_error"])
    state["status"] = "ready"
    state["last_verified_at"] = iso_now()
    state.pop("last_verification_error", None)
    save_chatgpt_state(paths, state)
    write_chatgpt_summary(paths, state)
    return state


def mark_chatgpt_degraded(paths: LabPaths, reason: str) -> dict[str, Any]:
    state = load_chatgpt_state(paths)
    if not state:
        state = {"schema_version": 1}
    state.update({"status": "degraded", "last_verification_error": reason, "updated_at": iso_now()})
    save_chatgpt_state(paths, state)
    write_chatgpt_summary(paths, state)
    return state


def write_chatgpt_summary(paths: LabPaths, state: dict[str, Any]) -> None:
    """Write a committed, non-sensitive readiness summary.

    The actual Project and conversation URLs remain in ignored local state.
    """

    atomic_write_text(
        paths.setup / "CHATGPT_RESEARCH_PARTNER.md",
        f"""# ChatGPT research partner

- Status: **{state.get("status", "unconfigured")}**
- Browser mode: `{state.get("browser_mode", "not selected")}`
- Project configured: **{bool(state.get("project_url"))}**
- Project name: `{state.get("project_name", "not created")}`
- Required model label: `{state.get("selected_model_label", "not selected")}`
- Silent fallback: `{state.get("allow_silent_fallback", False)}`
- Last verified: `{state.get("last_verified_at", "never")}`

Project and conversation URLs, browser profile details, and login state are kept
under `.research-lab/local/`, which is excluded from Git. A temporary browser or
login failure degrades consultation capacity but does not corrupt or stop the
Planner–Executor state machine.
""",
    )


def _next_question_id(paths: LabPaths) -> str:
    numbers = []
    for directory in paths.consultations.glob("Q-*"):
        match = re.match(r"Q-(\d+)", directory.name)
        if match:
            numbers.append(int(match.group(1)))
    return f"Q-{max(numbers, default=0) + 1:04d}"


def get_consultation_route(paths: LabPaths, question_id: str) -> dict[str, Any]:
    routes = _load_conversation_routes(paths)
    route = routes.get(question_id)
    if not isinstance(route, dict):
        raise FileNotFoundError(f"No local ChatGPT route is recorded for {question_id}")
    return route


def prepare_consultation(
    paths: LabPaths,
    *,
    question: str,
    purpose: str,
    requester_role: str,
    context_files: list[str] | None = None,
    follow_up_to: str | None = None,
) -> Path:
    state = load_chatgpt_state(paths)
    if not state.get("project_url"):
        raise RuntimeError("Initialize the ChatGPT research project before preparing a consultation")
    if state.get("status") != "ready":
        raise RuntimeError(
            "Verify the saved ChatGPT Project and exact Pro model before preparing a consultation"
        )
    if not question.strip() or not purpose.strip() or not requester_role.strip():
        raise ValueError("question, purpose, and requester_role must be non-empty")

    follow_up_route: dict[str, Any] | None = None
    if follow_up_to:
        parent_dir = paths.consultations / follow_up_to
        parent_meta = read_json(parent_dir / "META.json", default={})
        if not isinstance(parent_meta, dict) or parent_meta.get("status") != "completed":
            raise ValueError(f"Follow-up parent {follow_up_to} is missing or incomplete")
        follow_up_route = get_consultation_route(paths, follow_up_to)

    normalized_context: list[str] = []
    for raw in context_files or []:
        candidate = Path(raw)
        path = candidate if candidate.is_absolute() else paths.root / candidate
        relative = safe_relpath(path, paths.root)
        if not path.exists():
            raise FileNotFoundError(f"Consultation context does not exist: {relative}")
        normalized_context.append(relative)
    if follow_up_route and follow_up_route.get("project_url") != state.get("project_url"):
        raise ValueError("Follow-up conversation belongs to a different ChatGPT Project")

    with lab_lock(paths, "consultation-ids"):
        question_id = _next_question_id(paths)
        directory = paths.consultations / question_id
        directory.mkdir(parents=True)
        metadata = {
            "schema_version": 1,
            "question_id": question_id,
            "purpose": purpose.strip(),
            "requester_role": requester_role.strip(),
            "question": question.strip(),
            "context_files": normalized_context,
            "follow_up_to": follow_up_to,
            "status": "prepared",
            "browser_mode": state.get("browser_mode"),
            "required_model_label": state.get("selected_model_label"),
            "project_route_saved_locally": True,
            "follow_up_route_saved_locally": bool(follow_up_route),
            "created_at": iso_now(),
        }
        atomic_write_json(directory / "META.json", metadata)
        context_lines = "\n".join(f"- `{item}`" for item in metadata["context_files"]) or "- None"
        mode = "FOLLOW-UP" if follow_up_to else "NEW CHAT"
        lineage = f"Parent consultation: `{follow_up_to}`\n\n" if follow_up_to else ""
        atomic_write_text(
            directory / "REQUEST.md",
            f"""# ChatGPT consultation {question_id}

Mode: **{mode}**

{lineage}Requested by: `{requester_role}`

Purpose: {purpose}

## Question

{question.strip()}

## Context files

{context_lines}

## Instructions to the research partner

Act as a general senior research partner. Do not stay inside the framing of the
question if the framing itself is weak. Separate observations, assumptions,
inferences, and recommendations. Propose the cheapest evidence that would
discriminate between competing explanations. Surface cross-domain analogies and
high-upside alternatives when relevant. Do not claim experimental evidence that
is not present in the provided context.

Return:

1. Reframing or key assumptions
2. Strongest analysis
3. Alternative explanations or approaches
4. Recommended next evidence or experiment
5. Conditions that should reverse the recommendation
6. Confidence and important uncertainty
""",
        )
        atomic_write_text(directory / "RESPONSE.md", "# ChatGPT response\n\nPending browser execution.\n")
        return directory


def record_consultation_response(
    paths: LabPaths,
    *,
    question_id: str,
    conversation_url: str,
    response_text: str,
    actual_model_label: str,
) -> dict[str, Any]:
    directory = paths.consultations / question_id
    metadata = read_json(directory / "META.json", default={})
    if not metadata:
        raise FileNotFoundError(f"Unknown consultation {question_id}")
    expected = metadata.get("required_model_label")
    if actual_model_label != expected:
        raise ValueError(f"Expected ChatGPT model label {expected!r}; got {actual_model_label!r}")
    if not _is_chatgpt_url(conversation_url):
        raise ValueError("conversation_url must be an https://chatgpt.com URL")
    if not response_text.strip():
        raise ValueError("response_text must not be empty")
    atomic_write_text(directory / "RESPONSE.md", f"# ChatGPT response\n\n{response_text.strip()}\n")
    metadata.update(
        {
            "status": "completed",
            "conversation_route_saved_locally": True,
            "actual_model_label": actual_model_label,
            "completed_at": iso_now(),
        }
    )
    atomic_write_json(directory / "META.json", metadata)
    routes = _load_conversation_routes(paths)
    routes[question_id] = {
        "project_url": load_chatgpt_state(paths).get("project_url"),
        "conversation_url": conversation_url,
        "model_label": actual_model_label,
        "recorded_at": iso_now(),
    }
    _save_conversation_routes(paths, routes)
    return metadata


def record_consultation_synthesis(
    paths: LabPaths,
    *,
    question_id: str,
    synthesis_text: str,
) -> dict[str, Any]:
    """Persist the bounded, evidence-oriented result that may enter another role's context.

    The full advisor response remains archived in RESPONSE.md. Only this explicit
    synthesis is eligible for automatic Planner context loading, which avoids
    importing long browser transcripts or unreviewed claims.
    """

    directory = paths.consultations / question_id
    metadata = read_json(directory / "META.json", default={})
    if not isinstance(metadata, dict) or metadata.get("status") != "completed":
        raise ValueError(f"Consultation {question_id} must be completed before synthesis")
    if not synthesis_text.strip():
        raise ValueError("synthesis_text must not be empty")
    atomic_write_text(
        directory / "SYNTHESIS.md",
        f"# Bounded consultation synthesis — {question_id}\n\n{synthesis_text.strip()}\n",
    )
    metadata["synthesized_at"] = iso_now()
    metadata["synthesis_available"] = True
    atomic_write_json(directory / "META.json", metadata)
    return metadata
