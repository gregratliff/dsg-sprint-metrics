"""Category breakdown metric: points per work category."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from sprint_metrics.models import WorkItem


def _empty_category() -> dict[str, float | int]:
    return {"points": 0.0, "count": 0}


def calculate_category_breakdown(
    work_items: list[WorkItem], categories: list[str],
) -> dict[str, Any]:
    cat_set = set(categories)

    team: dict[str, dict[str, float | int]] = {cat: _empty_category() for cat in categories}
    team["other"] = _empty_category()

    per_person: dict[str, dict[str, dict[str, float | int]]] = defaultdict(
        lambda: {cat: _empty_category() for cat in [*categories, "other"]}
    )

    for wi in work_items:
        cat = wi.category if wi.category in cat_set else "other"
        pts = wi.story_points or 0.0

        team[cat]["points"] = float(team[cat]["points"]) + pts
        team[cat]["count"] = int(team[cat]["count"]) + 1

        per_person[wi.assigned_to][cat]["points"] = float(per_person[wi.assigned_to][cat]["points"]) + pts
        per_person[wi.assigned_to][cat]["count"] = int(per_person[wi.assigned_to][cat]["count"]) + 1

    return {
        "team": team,
        "individual": dict(per_person),
    }
