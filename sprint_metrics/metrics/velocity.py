"""Velocity metric: planned vs delivered story points."""
from __future__ import annotations

from collections import defaultdict

from sprint_metrics.models import WorkItem

CLOSED_STATES = {"Closed", "Done", "Resolved"}


def calculate_velocity(work_items: list[WorkItem]) -> dict:
    per_person: dict[str, dict[str, float]] = defaultdict(
        lambda: {"planned_points": 0.0, "delivered_points": 0.0}
    )

    team_planned = 0.0
    team_delivered = 0.0

    for wi in work_items:
        pts = wi.story_points
        if not pts:
            continue

        person = wi.assigned_to
        per_person[person]["planned_points"] += pts
        team_planned += pts

        if wi.state in CLOSED_STATES:
            per_person[person]["delivered_points"] += pts
            team_delivered += pts

    delivery_rate = team_delivered / team_planned if team_planned > 0 else 0.0

    return {
        "team": {
            "planned_points": team_planned,
            "delivered_points": team_delivered,
            "delivery_rate": delivery_rate,
        },
        "individual": dict(per_person),
    }
