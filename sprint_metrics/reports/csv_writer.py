"""CSV report writer for sprint metrics."""
from __future__ import annotations

import csv


def write_sprint_report(metrics: dict, output_path: str) -> None:
    sprint_name = metrics["sprint_name"]
    velocity = metrics["velocity"]
    cycle_time = metrics["cycle_time"]
    pr_cycle_time = metrics["pr_cycle_time"]
    rework = metrics["rework"]
    categories = metrics["categories"]

    # Determine category columns from team data (exclude "other" if empty)
    cat_names = [c for c in categories["team"] if c != "other" or categories["team"]["other"]["count"] > 0]

    fieldnames = [
        "sprint",
        "member",
        "planned_points",
        "delivered_points",
        "delivery_rate",
        "avg_cycle_time_days",
        "median_cycle_time_days",
        "cycle_time_count",
        "avg_pr_cycle_time_hours",
        "median_pr_cycle_time_hours",
        "pr_count",
        "rework_count",
        "rework_points",
        "rework_rate",
    ]
    for cat in cat_names:
        fieldnames.append(f"{cat}_points")
        fieldnames.append(f"{cat}_count")

    # Collect all individual members
    members = set()
    members.update(velocity["individual"].keys())
    members.update(cycle_time["individual"].keys())
    members.update(pr_cycle_time["individual"].keys())
    members.update(rework["individual"].keys())
    members.update(categories["individual"].keys())

    rows = []

    # Team row
    rows.append(_build_row(
        sprint_name, "TEAM",
        velocity["team"], cycle_time["team"], pr_cycle_time["team"],
        rework["team"], categories["team"], cat_names,
    ))

    # Individual rows
    for member in sorted(members):
        rows.append(_build_row(
            sprint_name, member,
            velocity["individual"].get(member, {}),
            cycle_time["individual"].get(member, {}),
            pr_cycle_time["individual"].get(member, {}),
            rework["individual"].get(member, {}),
            categories["individual"].get(member, {}),
            cat_names,
        ))

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _build_row(
    sprint: str,
    member: str,
    vel: dict,
    ct: dict,
    pr_ct: dict,
    rw: dict,
    cats: dict,
    cat_names: list[str],
) -> dict:
    row = {
        "sprint": sprint,
        "member": member,
        "planned_points": vel.get("planned_points", ""),
        "delivered_points": vel.get("delivered_points", ""),
        "delivery_rate": vel.get("delivery_rate", ""),
        "avg_cycle_time_days": ct.get("average_days", ""),
        "median_cycle_time_days": ct.get("median_days", ""),
        "cycle_time_count": ct.get("count", ""),
        "avg_pr_cycle_time_hours": pr_ct.get("average_hours", ""),
        "median_pr_cycle_time_hours": pr_ct.get("median_hours", ""),
        "pr_count": pr_ct.get("count", ""),
        "rework_count": rw.get("rework_count", ""),
        "rework_points": rw.get("rework_points", ""),
        "rework_rate": rw.get("rework_rate", ""),
    }
    for cat in cat_names:
        cat_data = cats.get(cat, {})
        row[f"{cat}_points"] = cat_data.get("points", "")
        row[f"{cat}_count"] = cat_data.get("count", "")
    return row
