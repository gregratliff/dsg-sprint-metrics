"""CLI entrypoint for sprint metrics collection."""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from sprint_metrics.clients.azure_devops_client import AzureDevOpsClient
from sprint_metrics.clients.github_client import GitHubClient
from sprint_metrics.config import Config, TeamMember, load_config
from sprint_metrics.metrics.category_breakdown import calculate_category_breakdown
from sprint_metrics.metrics.cycle_time import calculate_cycle_times
from sprint_metrics.metrics.pr_cycle_time import calculate_pr_cycle_times
from sprint_metrics.metrics.rework import calculate_rework
from sprint_metrics.metrics.velocity import calculate_velocity
from sprint_metrics.models import PullRequest, ScopeStatus, WorkItem
from sprint_metrics.reports.csv_writer import write_sprint_report

logger = logging.getLogger(__name__)


def normalize_metrics_identity(
    metrics: dict[str, Any], team_members: list[TeamMember],
) -> dict[str, Any]:
    """Remap metric dict keys from ADO/GitHub identities to display names.

    ADO-keyed metrics (velocity, cycle_time, rework, categories) use ado_identity.
    GitHub-keyed metrics (pr_cycle_time) use github_username.
    This function normalises both to TeamMember.name and attaches member_info.
    """
    ado_to_name = {m.ado_identity: m.name for m in team_members}
    gh_to_name = {m.github_username: m.name for m in team_members}

    ado_keyed = ["velocity", "cycle_time", "rework", "categories"]
    gh_keyed = ["pr_cycle_time"]

    result: dict[str, Any] = dict(metrics)

    for key in ado_keyed:
        if key in result and "individual" in result[key]:
            old = result[key]["individual"]
            result[key] = dict(result[key])
            result[key]["individual"] = {
                ado_to_name[k]: v for k, v in old.items() if k in ado_to_name
            }

    for key in gh_keyed:
        if key in result and "individual" in result[key]:
            old = result[key]["individual"]
            result[key] = dict(result[key])
            result[key]["individual"] = {
                gh_to_name[k]: v for k, v in old.items() if k in gh_to_name
            }

    # Build member_info lookup
    result["member_info"] = {
        m.name: {"ado_identity": m.ado_identity, "github_username": m.github_username}
        for m in team_members
    }

    return result


def filter_work_items_to_team(
    work_items: list[WorkItem], team_identities: set[str],
) -> list[WorkItem]:
    """Keep only work items assigned to configured team members."""
    return [wi for wi in work_items if wi.assigned_to in team_identities]


def _is_different_sprint(
    current_iteration: str, sprint_iteration: str,
) -> bool:
    """Return True if current_iteration is a different sprint, not just the backlog.

    An item moved to a parent/prefix of the sprint iteration path is on the backlog.
    An item moved to a sibling or unrelated iteration path is in a different sprint.
    """
    if not current_iteration or not sprint_iteration:
        return False
    # If the sprint path starts with the current path, the item was moved to
    # a parent (backlog), not a different sprint.
    if sprint_iteration.startswith(current_iteration):
        return False
    return current_iteration != sprint_iteration


def classify_sprint_scope(
    planned_items: list[WorkItem],
    end_of_sprint_items: list[WorkItem],
    *,
    current_items_by_id: dict[int, WorkItem] | None = None,
    sprint_iteration_path: str = "",
) -> list[WorkItem]:
    """Classify work items by comparing planning snapshot vs end-of-sprint snapshot.

    Returns unified list with scope_status set on each item:
    - COMMITTED: in both snapshots (uses end-of-sprint data for current state)
    - REMOVED: only in planning snapshot and not moved to another sprint
    - CARRIED_OVER: only in planning snapshot but moved to a different sprint iteration
    - ADDED_MID_SPRINT: only in end-of-sprint snapshot (scope creep)

    When current_items_by_id is provided, items missing from the end-of-sprint
    snapshot are checked against their current iteration path to distinguish
    true removals from items carried over to another sprint.
    """
    planned_by_id = {wi.id: wi for wi in planned_items}
    end_by_id = {wi.id: wi for wi in end_of_sprint_items}

    planned_ids = set(planned_by_id.keys())
    end_ids = set(end_by_id.keys())

    result: list[WorkItem] = []

    # Items in both — committed, use end-of-sprint data (more current)
    for wi_id in planned_ids & end_ids:
        wi = end_by_id[wi_id]
        wi.scope_status = ScopeStatus.COMMITTED
        result.append(wi)

    # Items only in planning — removed or carried over
    for wi_id in planned_ids - end_ids:
        current_wi = (current_items_by_id or {}).get(wi_id)
        if current_wi and _is_different_sprint(
            current_wi.iteration_path, sprint_iteration_path,
        ):
            current_wi.scope_status = ScopeStatus.CARRIED_OVER
            result.append(current_wi)
        else:
            wi = planned_by_id[wi_id]
            wi.scope_status = ScopeStatus.REMOVED
            result.append(wi)

    # Items only in end-of-sprint — added mid-sprint
    for wi_id in end_ids - planned_ids:
        wi = end_by_id[wi_id]
        wi.scope_status = ScopeStatus.ADDED_MID_SPRINT
        result.append(wi)

    return result


def _strip_revert_wrappers(title: str) -> str:
    """Strip leading Revert \"...\" wrappers to get the original PR title."""
    while title.startswith('Revert "'):
        title = title[len('Revert "'):]
        if title.endswith('"'):
            title = title[:-1]
    return title


def filter_excluded_prs(prs: list[PullRequest], patterns: list[str]) -> list[PullRequest]:
    """Remove PRs whose title matches any of the exclude patterns.

    Also matches Revert chains — e.g., Revert "Revert "develop -> master""
    is excluded if "develop -> master" matches a pattern.
    """
    if not patterns:
        return prs
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    return [
        pr for pr in prs
        if not any(rx.search(_strip_revert_wrappers(pr.title)) for rx in compiled)
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect sprint metrics from ADO and GitHub")
    parser.add_argument("--config", required=True, help="Path to config YAML file")
    parser.add_argument("--output-dir", default=".", help="Directory for CSV output")
    parser.add_argument("--dry-run", action="store_true", help="Validate config without calling APIs")
    parser.add_argument("--sprint-name", default=None, help="Override sprint name from config")
    return parser.parse_args(argv)


def _create_ado_client(cfg: Config) -> AzureDevOpsClient:
    from azure.devops.connection import Connection
    from azure.devops.credentials import BasicAuthentication

    pat = os.environ.get(cfg.azure_devops.pat_env_var)
    credentials = BasicAuthentication("", pat)
    connection = Connection(
        base_url=f"https://dev.azure.com/{cfg.azure_devops.organization}",
        creds=credentials,
    )
    return AzureDevOpsClient(
        connection=connection,
        project=cfg.azure_devops.project,
        category_field=cfg.azure_devops.category_field,
    )


def _create_github_client(cfg: Config) -> GitHubClient:
    from github import Auth, Github

    pat = os.environ.get(cfg.github.pat_env_var, "")
    return GitHubClient(github=Github(auth=Auth.Token(pat)))


def run(
    config_path: str,
    output_dir: str = ".",
    dry_run: bool = False,
    sprint_name: str | None = None,
) -> None:
    cfg = load_config(config_path)

    # CLI --sprint-name overrides config sprint.name
    if sprint_name is not None:
        cfg.sprint.name = sprint_name

    # Validate PATs exist
    for env_var in [cfg.azure_devops.pat_env_var, cfg.github.pat_env_var]:
        if not os.environ.get(env_var):
            logger.error("Environment variable '%s' is not set", env_var)
            sys.exit(1)

    if dry_run:
        logger.info(
            "Config validated: sprint='%s', %d team members, %d categories",
            cfg.sprint.name, len(cfg.team_members), len(cfg.categories),
        )
        return

    ado_client = _create_ado_client(cfg)
    gh_client = _create_github_client(cfg)

    # Build iteration path from project + stem + sprint name
    iteration_path = f"{cfg.azure_devops.project}\\{cfg.sprint.stem}\\{cfg.sprint.name}"
    team_identities = {m.ado_identity for m in cfg.team_members}

    # Calculate planning snapshot date
    planning_date = cfg.sprint.start_date + timedelta(days=cfg.sprint.planning_offset_days)
    if planning_date > cfg.sprint.end_date:
        logger.warning(
            "planning_offset_days (%d) exceeds sprint duration — clamping to end_date",
            cfg.sprint.planning_offset_days,
        )
        planning_date = cfg.sprint.end_date

    # Ensure dates are timezone-aware for ASOF queries
    if planning_date.tzinfo is None:
        planning_date = planning_date.replace(tzinfo=UTC)
    end_date = cfg.sprint.end_date
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=UTC)

    # Fetch planning snapshot (what was in sprint after planning settled)
    logger.info("Fetching planning snapshot (as of %s)...", planning_date.date())
    planned_items = ado_client.get_sprint_work_items_asof(iteration_path, planning_date)
    logger.info("Planning snapshot: %d work items", len(planned_items))

    # Fetch end-of-sprint snapshot
    now = datetime.now(tz=UTC)
    if end_date <= now:
        logger.info("Fetching end-of-sprint snapshot (as of %s)...", end_date.date())
        end_items = ado_client.get_sprint_work_items_asof(iteration_path, end_date)
    else:
        logger.info("Sprint still in progress — using current state...")
        end_items = ado_client.get_sprint_work_items(iteration_path)
    logger.info("End-of-sprint snapshot: %d work items", len(end_items))

    # Filter both snapshots to team members
    planned_items = filter_work_items_to_team(planned_items, team_identities)
    end_items = filter_work_items_to_team(end_items, team_identities)

    # Identify items that left the sprint (in planned but not end-of-sprint)
    planned_ids = {wi.id for wi in planned_items}
    end_ids = {wi.id for wi in end_items}
    removed_ids = sorted(planned_ids - end_ids)

    # Fetch current state of removed items to distinguish carryover vs true removal
    current_items_by_id: dict[int, WorkItem] = {}
    if removed_ids:
        logger.info(
            "Fetching current state of %d items removed from sprint...",
            len(removed_ids),
        )
        current_items = ado_client.get_work_items_by_ids(removed_ids)
        current_items_by_id = {wi.id: wi for wi in current_items}

    # Classify scope
    work_items = classify_sprint_scope(
        planned_items, end_items,
        current_items_by_id=current_items_by_id,
        sprint_iteration_path=iteration_path,
    )

    # Log scope changes
    for wi in work_items:
        if wi.scope_status == ScopeStatus.REMOVED:
            logger.warning(
                "Work item %d (%s) removed from sprint — %.1f points descoped",
                wi.id, wi.title, wi.story_points or 0,
            )
        elif wi.scope_status == ScopeStatus.CARRIED_OVER:
            logger.info(
                "Work item %d (%s) carried over to %s — %.1f points",
                wi.id, wi.title, wi.iteration_path, wi.story_points or 0,
            )
        elif wi.scope_status == ScopeStatus.ADDED_MID_SPRINT:
            logger.info(
                "Work item %d (%s) added mid-sprint — %.1f points",
                wi.id, wi.title, wi.story_points or 0,
            )

    all_prs: list[PullRequest] = []
    team_usernames = [m.github_username for m in cfg.team_members]
    for repo_name in cfg.github.repos:
        repo_full = f"{cfg.github.org}/{repo_name}"
        logger.info("Fetching PRs from %s...", repo_full)
        try:
            prs = gh_client.get_pull_requests(
                repo=repo_full,
                start_date=cfg.sprint.start_date,
                end_date=cfg.sprint.end_date,
                team_usernames=team_usernames,
            )
            all_prs.extend(prs)
        except Exception:
            logger.warning("Failed to fetch PRs from %s — skipping this repo", repo_full)

    logger.info("Total: %d PRs across %d repos", len(all_prs), len(cfg.github.repos))

    # Filter deployment / excluded PRs
    if cfg.github.pr_exclude_patterns:
        before = len(all_prs)
        all_prs = filter_excluded_prs(all_prs, cfg.github.pr_exclude_patterns)
        excluded = before - len(all_prs)
        if excluded:
            logger.info("Excluded %d PRs matching exclude patterns", excluded)

    # Warn about PRs with no work item reference
    for pr in all_prs:
        if not pr.extract_work_item_ids():
            logger.warning(
                "PR #%d (%s) has no work item reference", pr.number, pr.author,
            )

    # Fetch work items referenced in PRs but missing from sprint query
    existing_wi_ids = {wi.id for wi in work_items}
    # Build mapping: work_item_id -> list of (PR number, PR author) for diagnostics
    wi_id_to_prs: dict[int, list[tuple[int, str]]] = {}
    for pr in all_prs:
        for wi_id in pr.extract_work_item_ids():
            wi_id_to_prs.setdefault(wi_id, []).append((pr.number, pr.author))
    missing_ids = sorted(set(wi_id_to_prs.keys()) - existing_wi_ids)
    if missing_ids:
        logger.info(
            "Fetching %d PR-referenced work items not in sprint query...",
            len(missing_ids),
        )
        extra_items = ado_client.get_work_items_by_ids(missing_ids)
        returned_ids = {wi.id for wi in extra_items}
        # Warn about IDs that weren't found, with the PR that referenced them
        for wid in missing_ids:
            if wid not in returned_ids:
                for pr_number, pr_author in wi_id_to_prs[wid]:
                    logger.warning(
                        "Work item %d not found — referenced by PR #%d (%s)",
                        wid, pr_number, pr_author,
                    )
        # Only keep items assigned to team members
        extra_items = filter_work_items_to_team(extra_items, team_identities)
        if extra_items:
            logger.info("  Added %d work items from PR references", len(extra_items))
            work_items.extend(extra_items)

    # Calculate metrics
    metrics: dict[str, Any] = {
        "sprint_name": cfg.sprint.name,
        "velocity": calculate_velocity(work_items),
        "cycle_time": calculate_cycle_times(work_items),
        "pr_cycle_time": calculate_pr_cycle_times(all_prs),
        "rework": calculate_rework(work_items, cfg.azure_devops.rework_labels),
        "categories": calculate_category_breakdown(work_items, cfg.categories),
    }

    # Normalize identities to display names
    metrics = normalize_metrics_identity(metrics, cfg.team_members)

    # Write report
    safe_name = cfg.sprint.name.replace("\\", "_").replace("/", "_").replace(" ", "_")
    output_path = os.path.join(output_dir, f"{safe_name}_report.csv")
    try:
        write_sprint_report(metrics, output_path)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to write report to '{output_path}': {exc}"
        ) from exc
    logger.info("Report written to %s", output_path)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    args = parse_args()
    run(config_path=args.config, output_dir=args.output_dir, dry_run=args.dry_run,
        sprint_name=args.sprint_name)


if __name__ == "__main__":
    main()
