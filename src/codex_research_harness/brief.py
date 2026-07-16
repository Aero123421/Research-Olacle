from __future__ import annotations

from typing import Any

from .jobs import gpu_queue
from .models import LabPaths
from .utils import atomic_write_text, read_json

STATUS_JA = {
    "draft": "準備中",
    "ready": "開始可能",
    "running": "研究中",
    "paused": "一時停止",
    "completed": "完了",
    "blocked": "外部要因で停止",
}


def _latest_campaign(paths: LabPaths) -> tuple[str | None, dict[str, Any]]:
    candidates = sorted(path for path in paths.campaigns.glob("C-*") if path.is_dir())
    if not candidates:
        return None, {}
    directory = candidates[-1]
    return directory.name, read_json(directory / "STATE.json", default={})


def generate_human_brief(paths: LabPaths) -> str:
    campaign_id, state = _latest_campaign(paths)
    if not campaign_id:
        text = """# 現在の研究状況

**状態:** 研究計画の準備中

現在はResearch Plannerが曖昧な目標、データ、ルール、既存研究を整理し、最初の明確な研究Campaignを設計する段階です。

**次:** Campaign Contractを作成し、設定済みResearch Executorプロファイルで`/goal`研究を開始します。
"""
        atomic_write_text(paths.research / "CURRENT_BRIEF.md", text)
        return text
    resources = state.get("resources", {})
    forecast = state.get("forecast", {})
    progress = state.get("progress", {})
    status = STATUS_JA.get(state.get("status"), state.get("status", "不明"))
    next_actions = state.get("next_actions", [])
    next_text = "\n".join(f"- {item}" for item in next_actions[:3]) or "- 未記録"
    queue = gpu_queue(paths)
    queue_text = (
        "\n".join(
            f"- {'実行中' if job.get('status') == 'running' else '待機'}: "
            f"{job.get('campaign_id')} / {job.get('name')} / 予定{job.get('planned_hours', 0)}時間"
            for job in queue[:4]
        )
        or "- 現在、GPUの実行・待機ジョブはありません"
    )
    text = f"""# 現在の研究状況

**状態:** {status}

**Campaign:** `{campaign_id}`

**現在:** {state.get("current_action", "状態未記録")}

## 進み具合

- マイルストーン: {progress.get("completed_milestones", 0)} / {progress.get("total_milestones", 0)}
- 壁時計: {resources.get("wall_hours_used", 0)}時間
- GPU: {resources.get("gpu_hours_used", 0)}時間
- 費用: {resources.get("cost_jpy", 0)}円
- 終了予測: {forecast.get("finish_low") or "未推定"} ～ {forecast.get("finish_high") or "未推定"}

## 次に行うこと

{next_text}

## GPUの順番

{queue_text}

## 人間の役割

研究判断はAI研究ループが自律的に行います。人間は研究所が正常に動き、証拠が増え、時間・GPU予算が守られているかを観察します。
"""
    atomic_write_text(paths.research / "CURRENT_BRIEF.md", text)
    return text
