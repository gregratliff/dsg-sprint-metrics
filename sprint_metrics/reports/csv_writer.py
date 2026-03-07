"""CSV report writer for sprint metrics."""
from __future__ import annotations

import csv
from typing import Any


def write_sprint_report(metrics: dict[str, Any], output_path: str) -> None:
    sprint_name: str = metrics["sprint_name"]
    velocity: dict[str, Any] = metrics["velocity"]
    cycle_time: dict[str, Any] = metrics["cycle_time"]
    pr_cycle_time: dict[str, Any] = metrics["pr_cycle_time"]
    rework: dict[str, Any] = metrics["rework"]
    categories: dict[str, Any] = metrics["categories"]

    # Determine category columns from team data (exclude "other" if empty)
    cat_names = [c for c in categories["team"] if c != "other" or categories["team"]["other"]["count"] > 0]

    member_info: dict[str, dict[str, str]] = metrics.get("member_info", {})

    fieldnames = [
        "sprint",
        "member",
        "ado_identity",
        "github_username",
        "planned_points",
        "delivered_points",
        "delivery_rate",
        "scope_added_points",
        "scope_removed_points",
        "carryover_points",
        "carryover_rate",
        "commitment_reliability",
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
    members: set[str] = set()
    members.update(velocity["individual"].keys())
    members.update(cycle_time["individual"].keys())
    members.update(pr_cycle_time["individual"].keys())
    members.update(rework["individual"].keys())
    members.update(categories["individual"].keys())

    rows: list[dict[str, Any]] = []

    # Team row
    rows.append(_build_row(
        sprint_name, "TEAM", "", "",
        velocity["team"], cycle_time["team"], pr_cycle_time["team"],
        rework["team"], categories["team"], cat_names,
    ))

    # Individual rows
    for member in sorted(members):
        info = member_info.get(member, {})
        rows.append(_build_row(
            sprint_name, member,
            info.get("ado_identity", ""),
            info.get("github_username", ""),
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
    ado_identity: str,
    github_username: str,
    vel: dict[str, Any],
    ct: dict[str, Any],
    pr_ct: dict[str, Any],
    rw: dict[str, Any],
    cats: dict[str, Any],
    cat_names: list[str],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "sprint": sprint,
        "member": member,
        "ado_identity": ado_identity,
        "github_username": github_username,
        "planned_points": vel.get("planned_points", ""),
        "delivered_points": vel.get("delivered_points", ""),
        "delivery_rate": vel.get("delivery_rate", ""),
        "scope_added_points": vel.get("scope_added_points", ""),
        "scope_removed_points": vel.get("scope_removed_points", ""),
        "carryover_points": vel.get("carryover_points", ""),
        "carryover_rate": vel.get("carryover_rate", ""),
        "commitment_reliability": vel.get("commitment_reliability", ""),
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
        cat_data: dict[str, Any] = cats.get(cat, {})
        row[f"{cat}_points"] = cat_data.get("points", "")
        row[f"{cat}_count"] = cat_data.get("count", "")
    return row
