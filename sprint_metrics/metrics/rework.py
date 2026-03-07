"""Rework metric: items tagged with rework labels by QA."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from sprint_metrics.models import WorkItem


def _is_rework(labels: list[str], rework_labels: set[str]) -> bool:
    return any(label.lower() in rework_labels for label in labels)


def calculate_rework(work_items: list[WorkItem], rework_labels: list[str]) -> dict[str, Any]:
    rework_set = {label.lower() for label in rework_labels}

    per_person: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"rework_count": 0, "rework_points": 0.0, "total_count": 0}
    )

    team_rework = 0
    team_rework_points = 0.0
    total = len(work_items)

    for wi in work_items:
        person = wi.assigned_to
        per_person[person]["total_count"] = int(per_person[person]["total_count"]) + 1

        if _is_rework(wi.labels, rework_set):
            team_rework += 1
            pts = wi.story_points or 0.0
            team_rework_points += pts
            per_person[person]["rework_count"] = int(per_person[person]["rework_count"]) + 1
            per_person[person]["rework_points"] = float(per_person[person]["rework_points"]) + pts

    return {
        "team": {
            "rework_count": team_rework,
            "rework_points": team_rework_points,
            "total_count": total,
            "rework_rate": team_rework / total if total > 0 else 0.0,
        },
        "individual": dict(per_person),
    }
