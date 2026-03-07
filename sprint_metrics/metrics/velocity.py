"""Velocity metric: planned vs delivered story points with scope tracking."""
from __future__ import annotations

from collections import defaultdict

from sprint_metrics.models import ScopeStatus, WorkItem

CLOSED_STATES = {"Closed", "Done", "Resolved"}

# Scope statuses that count toward "planned" (items in the planning snapshot)
_PLANNED_STATUSES = {ScopeStatus.COMMITTED, ScopeStatus.REMOVED, ScopeStatus.CARRIED_OVER}
# Scope statuses that can contribute to "delivered" (items in end-of-sprint snapshot)
_DELIVERABLE_STATUSES = {ScopeStatus.COMMITTED, ScopeStatus.ADDED_MID_SPRINT}
# Scope statuses that can carry over (not completed within the sprint)
_CARRYOVER_STATUSES = {ScopeStatus.COMMITTED, ScopeStatus.ADDED_MID_SPRINT, ScopeStatus.CARRIED_OVER}
# Scope statuses that count as "removed from sprint" (descoped or carried over)
_SCOPE_REMOVED_STATUSES = {ScopeStatus.REMOVED, ScopeStatus.CARRIED_OVER}


def _empty_accum() -> dict[str, float]:
    return {
        "planned_points": 0.0,
        "delivered_points": 0.0,
        "committed_delivered": 0.0,
        "scope_added_points": 0.0,
        "scope_removed_points": 0.0,
        "carryover_points": 0.0,
    }


def _finalize(acc: dict[str, float]) -> dict[str, float]:
    """Compute derived rates from accumulated counters."""
    planned = acc["planned_points"]
    delivered = acc["delivered_points"]
    committed_delivered = acc.pop("committed_delivered")
    return {
        **acc,
        "delivery_rate": delivered / planned if planned > 0 else 0.0,
        "carryover_rate": acc["carryover_points"] / planned if planned > 0 else 0.0,
        "commitment_reliability": committed_delivered / planned if planned > 0 else 0.0,
    }


def _accumulate(acc: dict[str, float], wi: WorkItem, pts: float) -> None:
    """Accumulate a single work item's points into an accumulator dict."""
    is_closed = wi.state in CLOSED_STATES

    if wi.scope_status in _PLANNED_STATUSES:
        acc["planned_points"] += pts

    if is_closed and wi.scope_status in _DELIVERABLE_STATUSES:
        acc["delivered_points"] += pts
        if wi.scope_status == ScopeStatus.COMMITTED:
            acc["committed_delivered"] += pts

    if wi.scope_status == ScopeStatus.ADDED_MID_SPRINT:
        acc["scope_added_points"] += pts
    elif wi.scope_status in _SCOPE_REMOVED_STATUSES:
        acc["scope_removed_points"] += pts

    if wi.scope_status == ScopeStatus.CARRIED_OVER:
        acc["carryover_points"] += pts
    elif not is_closed and wi.scope_status in _CARRYOVER_STATUSES:
        acc["carryover_points"] += pts


def calculate_velocity(work_items: list[WorkItem]) -> dict:
    team_acc = _empty_accum()
    per_person: dict[str, dict[str, float]] = defaultdict(_empty_accum)

    for wi in work_items:
        pts = wi.story_points
        if not pts:
            continue

        _accumulate(team_acc, wi, pts)
        _accumulate(per_person[wi.assigned_to], wi, pts)

    return {
        "team": _finalize(team_acc),
        "individual": {person: _finalize(acc) for person, acc in per_person.items()},
    }
