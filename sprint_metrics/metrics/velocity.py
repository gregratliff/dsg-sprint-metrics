"""Velocity metric: planned vs delivered story points with scope tracking."""
from __future__ import annotations

from collections import defaultdict

from sprint_metrics.models import ScopeStatus, WorkItem

CLOSED_STATES = {"Closed", "Done", "Resolved"}

# Scope statuses that count toward "planned" (items in the planning snapshot)
_PLANNED_STATUSES = {ScopeStatus.COMMITTED, ScopeStatus.REMOVED}
# Scope statuses that can contribute to "delivered" (items in end-of-sprint snapshot)
_DELIVERABLE_STATUSES = {ScopeStatus.COMMITTED, ScopeStatus.ADDED_MID_SPRINT}
# Scope statuses that can carry over (still in sprint but not closed)
_CARRYOVER_STATUSES = {ScopeStatus.COMMITTED, ScopeStatus.ADDED_MID_SPRINT}


def calculate_velocity(work_items: list[WorkItem]) -> dict:
    per_person: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "planned_points": 0.0,
            "delivered_points": 0.0,
        }
    )

    team_planned = 0.0
    team_delivered = 0.0
    team_committed_delivered = 0.0
    team_scope_added = 0.0
    team_scope_removed = 0.0
    team_carryover = 0.0

    for wi in work_items:
        pts = wi.story_points
        if not pts:
            continue

        person = wi.assigned_to
        is_closed = wi.state in CLOSED_STATES

        # Planned = items that were in the planning snapshot
        if wi.scope_status in _PLANNED_STATUSES:
            per_person[person]["planned_points"] += pts
            team_planned += pts

        # Delivered = closed items that are in the end-of-sprint snapshot
        if is_closed and wi.scope_status in _DELIVERABLE_STATUSES:
            per_person[person]["delivered_points"] += pts
            team_delivered += pts

            if wi.scope_status == ScopeStatus.COMMITTED:
                team_committed_delivered += pts

        # Scope tracking
        if wi.scope_status == ScopeStatus.ADDED_MID_SPRINT:
            team_scope_added += pts
        elif wi.scope_status == ScopeStatus.REMOVED:
            team_scope_removed += pts

        # Carryover = non-closed items still in the sprint
        if not is_closed and wi.scope_status in _CARRYOVER_STATUSES:
            team_carryover += pts

    delivery_rate = team_delivered / team_planned if team_planned > 0 else 0.0
    commitment_reliability = (
        team_committed_delivered / team_planned if team_planned > 0 else 0.0
    )
    carryover_rate = team_carryover / team_planned if team_planned > 0 else 0.0

    return {
        "team": {
            "planned_points": team_planned,
            "delivered_points": team_delivered,
            "delivery_rate": delivery_rate,
            "scope_added_points": team_scope_added,
            "scope_removed_points": team_scope_removed,
            "carryover_points": team_carryover,
            "carryover_rate": carryover_rate,
            "commitment_reliability": commitment_reliability,
        },
        "individual": dict(per_person),
    }
