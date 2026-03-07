"""PR cycle time metric: opened → merged."""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

from sprint_metrics.models import PullRequest


def calculate_pr_cycle_times(pull_requests: list[PullRequest]) -> dict[str, Any]:
    per_person: dict[str, list[float]] = defaultdict(list)
    all_times: list[float] = []

    for pr in pull_requests:
        ct = pr.cycle_time_hours
        if ct is None:
            continue
        all_times.append(ct)
        per_person[pr.author].append(ct)

    individual: dict[str, dict[str, float | int]] = {}
    for person, times in per_person.items():
        individual[person] = {
            "average_hours": sum(times) / len(times),
            "median_hours": median(times),
            "count": len(times),
        }

    return {
        "team": {
            "average_hours": sum(all_times) / len(all_times) if all_times else 0.0,
            "median_hours": median(all_times) if all_times else 0.0,
            "count": len(all_times),
        },
        "individual": individual,
    }
