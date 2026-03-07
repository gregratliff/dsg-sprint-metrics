"""Cycle time metric: work item activated → closed."""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

from sprint_metrics.models import ScopeStatus, WorkItem

# Only count cycle time for items that stayed in the sprint
_CYCLE_TIME_STATUSES = {ScopeStatus.COMMITTED, ScopeStatus.ADDED_MID_SPRINT}


def calculate_cycle_times(work_items: list[WorkItem]) -> dict[str, Any]:
    per_person: dict[str, list[float]] = defaultdict(list)
    all_times: list[float] = []

    for wi in work_items:
        if wi.scope_status not in _CYCLE_TIME_STATUSES:
            continue
        ct = wi.cycle_time_days
        if ct is None:
            continue
        all_times.append(ct)
        per_person[wi.assigned_to].append(ct)

    individual: dict[str, dict[str, float | int]] = {}
    for person, times in per_person.items():
        individual[person] = {
            "average_days": sum(times) / len(times),
            "median_days": median(times),
            "count": len(times),
        }

    return {
        "team": {
            "average_days": sum(all_times) / len(all_times) if all_times else 0.0,
            "median_days": median(all_times) if all_times else 0.0,
            "count": len(all_times),
        },
        "individual": individual,
    }
