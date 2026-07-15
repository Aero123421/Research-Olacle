from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from .jobs import gpu_queue
from .models import LabPaths
from .utils import atomic_write_text, read_json


def _campaigns(paths: LabPaths) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    values = []
    for directory in sorted(path for path in paths.campaigns.glob("C-*") if path.is_dir()):
        values.append(
            (
                directory.name,
                read_json(directory / "CONTRACT.json", default={}),
                read_json(directory / "STATE.json", default={}),
            )
        )
    return values


def generate_mermaid(paths: LabPaths) -> Path:
    lines = ["flowchart LR", '  M["Human Mission"] --> P["Research Planner"]']
    campaigns = _campaigns(paths)
    if not campaigns:
        lines.append('  P --> N["No campaign yet"]')
    for index, (campaign_id, contract, state) in enumerate(campaigns):
        node = f"C{index}"
        title = str(contract.get("title", campaign_id)).replace('"', "'")
        status = str(state.get("status", "unknown"))
        lines.append(f'  P --> {node}["{campaign_id}: {title}\\n{status}"]')
        lines.append(f"  {node} --> P")
    output = paths.reports / "visuals" / "research-loop.mmd"
    atomic_write_text(output, "\n".join(lines) + "\n")
    return output


def generate_gpu_svg(paths: LabPaths) -> Path:
    campaigns = _campaigns(paths)
    width = 1000
    row_height = 56
    height = max(180, 100 + row_height * max(1, len(campaigns)))
    max_gpu = max(
        [float(state.get("resources", {}).get("gpu_hours_used", 0)) for _, _, state in campaigns] + [1.0]
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="30" y="36" font-family="sans-serif" font-size="24" font-weight="bold">GPU usage by campaign</text>',
    ]
    if not campaigns:
        parts.append(
            '<text x="30" y="90" font-family="sans-serif" font-size="16">No campaign data yet.</text>'
        )
    for index, (campaign_id, contract, state) in enumerate(campaigns):
        y = 75 + index * row_height
        used = float(state.get("resources", {}).get("gpu_hours_used", 0))
        budget = float(contract.get("budget", {}).get("gpu_hours", 0))
        bar_width = 650 * (used / max(max_gpu, budget, 1.0))
        budget_width = 650 * (budget / max(max_gpu, budget, 1.0))
        parts.extend(
            [
                f'<text x="30" y="{y + 18}" font-family="sans-serif" font-size="14">{html.escape(campaign_id)}</text>',
                f'<rect x="150" y="{y}" width="{budget_width:.1f}" height="24" fill="#e5e7eb" rx="4"/>',
                f'<rect x="150" y="{y}" width="{bar_width:.1f}" height="24" fill="#2563eb" rx="4"/>',
                f'<text x="820" y="{y + 18}" font-family="sans-serif" font-size="14">{used:.1f} / {budget:.1f} GPU h</text>',
            ]
        )
    parts.append("</svg>")
    output = paths.reports / "visuals" / "gpu-usage.svg"
    atomic_write_text(output, "\n".join(parts) + "\n")
    return output


def generate_gpu_queue_svg(paths: LabPaths) -> Path:
    queue = gpu_queue(paths)
    width = 1100
    row_height = 62
    height = max(180, 105 + row_height * max(1, len(queue)))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="30" y="38" font-family="sans-serif" font-size="24" font-weight="bold">GPU queue: now and next</text>',
    ]
    if not queue:
        parts.append(
            '<text x="30" y="90" font-family="sans-serif" font-size="16">No active or queued GPU job.</text>'
        )
    for index, job in enumerate(queue, 1):
        y = 72 + (index - 1) * row_height
        status = str(job.get("status", "unknown"))
        label = (
            "NOW"
            if status == "running"
            else f"NEXT {index - (1 if queue and queue[0].get('status') == 'running' else 0)}"
        )
        details = f"{job.get('campaign_id')} • {job.get('name')} • {job.get('resource')} • planned {job.get('planned_hours', 0)} h"
        progress = str(job.get("progress") or status)
        fill = "#dbeafe" if status == "running" else "#f1f5f9"
        parts.extend(
            [
                f'<rect x="25" y="{y}" width="1050" height="46" rx="8" fill="{fill}"/>',
                f'<text x="42" y="{y + 20}" font-family="sans-serif" font-size="13" font-weight="bold">{html.escape(label)}</text>',
                f'<text x="150" y="{y + 20}" font-family="sans-serif" font-size="14">{html.escape(details)}</text>',
                f'<text x="150" y="{y + 39}" font-family="sans-serif" font-size="12" fill="#475569">{html.escape(progress)}</text>',
            ]
        )
    parts.append("</svg>")
    output = paths.reports / "visuals" / "gpu-queue.svg"
    atomic_write_text(output, "\n".join(parts) + "\n")
    return output


def generate_cockpit(paths: LabPaths) -> Path:
    campaigns = _campaigns(paths)
    rows = []
    for campaign_id, contract, state in campaigns:
        resources = state.get("resources", {})
        rows.append(
            "<tr>"
            f"<td>{html.escape(campaign_id)}</td>"
            f"<td>{html.escape(str(contract.get('title', '')))}</td>"
            f"<td>{html.escape(str(state.get('status', 'unknown')))}</td>"
            f"<td>{html.escape(str(state.get('current_action', '')))}</td>"
            f"<td>{resources.get('wall_hours_used', 0)}</td>"
            f"<td>{resources.get('gpu_hours_used', 0)}</td>"
            "</tr>"
        )
    body = "\n".join(rows) or '<tr><td colspan="6">No campaigns yet.</td></tr>'
    page = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Codex Research Harness Cockpit</title>
<style>
body{{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;margin:2rem;line-height:1.5;color:#111827;background:#f8fafc}}
main{{max-width:1200px;margin:auto;background:white;padding:2rem;border-radius:16px;box-shadow:0 8px 30px #0001}}
h1{{margin-top:0}} table{{border-collapse:collapse;width:100%}} th,td{{padding:.75rem;border-bottom:1px solid #e5e7eb;text-align:left}} th{{background:#f1f5f9}} .note{{color:#475569}}
</style>
</head>
<body><main>
<h1>AI Research Lab Cockpit</h1>
<p class="note">Human-facing snapshot generated from durable campaign state. Scientific decisions remain autonomous.</p>
<table><thead><tr><th>Campaign</th><th>Goal</th><th>Status</th><th>Current action</th><th>Wall h</th><th>GPU h</th></tr></thead><tbody>{body}</tbody></table>
</main></body></html>
"""
    output = paths.reports / "cockpit" / "index.html"
    atomic_write_text(output, page)
    return output


def generate_all(paths: LabPaths) -> list[Path]:
    return [
        generate_mermaid(paths),
        generate_gpu_svg(paths),
        generate_gpu_queue_svg(paths),
        generate_cockpit(paths),
    ]
