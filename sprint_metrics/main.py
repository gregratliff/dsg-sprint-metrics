"""CLI entrypoint for sprint metrics collection."""
from __future__ import annotations

import argparse
import os
import re
import sys

from sprint_metrics.config import load_config, Config
from sprint_metrics.clients.azure_devops_client import AzureDevOpsClient
from sprint_metrics.clients.github_client import GitHubClient
from sprint_metrics.metrics.velocity import calculate_velocity
from sprint_metrics.metrics.cycle_time import calculate_cycle_times
from sprint_metrics.metrics.pr_cycle_time import calculate_pr_cycle_times
from sprint_metrics.metrics.rework import calculate_rework
from sprint_metrics.metrics.category_breakdown import calculate_category_breakdown
from sprint_metrics.models import PullRequest, WorkItem
from sprint_metrics.reports.csv_writer import write_sprint_report


def normalize_metrics_identity(
    metrics: dict, team_members: list,
) -> dict:
    """Remap metric dict keys from ADO/GitHub identities to display names.

    ADO-keyed metrics (velocity, cycle_time, rework, categories) use ado_identity.
    GitHub-keyed metrics (pr_cycle_time) use github_username.
    This function normalises both to TeamMember.name and attaches member_info.
    """
    ado_to_name = {m.ado_identity: m.name for m in team_members}
    gh_to_name = {m.github_username: m.name for m in team_members}

    ado_keyed = ["velocity", "cycle_time", "rework", "categories"]
    gh_keyed = ["pr_cycle_time"]

    result = dict(metrics)

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


def filter_excluded_prs(prs: list[PullRequest], patterns: list[str]) -> list[PullRequest]:
    """Remove PRs whose title matches any of the exclude patterns."""
    if not patterns:
        return prs
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    return [pr for pr in prs if not any(rx.search(pr.title) for rx in compiled)]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect sprint metrics from ADO and GitHub")
    parser.add_argument("--config", required=True, help="Path to config YAML file")
    parser.add_argument("--output-dir", default=".", help="Directory for CSV output")
    parser.add_argument("--dry-run", action="store_true", help="Validate config without calling APIs")
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

    pat = os.environ.get(cfg.github.pat_env_var)
    return GitHubClient(github=Github(auth=Auth.Token(pat)))


def run(
    config_path: str,
    output_dir: str = ".",
    dry_run: bool = False,
) -> None:
    cfg = load_config(config_path)

    # Validate PATs exist
    for env_var in [cfg.azure_devops.pat_env_var, cfg.github.pat_env_var]:
        if not os.environ.get(env_var):
            print(f"Error: environment variable '{env_var}' is not set", file=sys.stderr)
            sys.exit(1)

    if dry_run:
        print(f"Config validated: sprint='{cfg.sprint.name}', "
              f"{len(cfg.team_members)} team members, "
              f"{len(cfg.categories)} categories")
        return

    ado_client = _create_ado_client(cfg)
    gh_client = _create_github_client(cfg)

    # Build iteration path from project + sprint name
    iteration_path = f"{cfg.azure_devops.project}\\{cfg.sprint.name}"

    # Fetch data
    print(f"Fetching ADO work items for '{iteration_path}'...")
    work_items = ado_client.get_sprint_work_items(iteration_path)
    print(f"Found {len(work_items)} work items")

    # Filter to configured team members only
    team_identities = {m.ado_identity for m in cfg.team_members}
    before = len(work_items)
    work_items = filter_work_items_to_team(work_items, team_identities)
    excluded = before - len(work_items)
    if excluded:
        print(f"Filtered out {excluded} work items not assigned to team members")

    all_prs = []
    team_usernames = [m.github_username for m in cfg.team_members]
    for repo_name in cfg.github.repos:
        repo_full = f"{cfg.github.org}/{repo_name}"
        print(f"Fetching PRs from {repo_full}...")
        prs = gh_client.get_pull_requests(
            repo=repo_full,
            start_date=cfg.sprint.start_date,
            end_date=cfg.sprint.end_date,
            team_usernames=team_usernames,
        )
        all_prs.extend(prs)

    print(f"Total: {len(all_prs)} PRs across {len(cfg.github.repos)} repos")

    # Filter deployment / excluded PRs
    if cfg.github.pr_exclude_patterns:
        before = len(all_prs)
        all_prs = filter_excluded_prs(all_prs, cfg.github.pr_exclude_patterns)
        excluded = before - len(all_prs)
        if excluded:
            print(f"Excluded {excluded} PRs matching exclude patterns")

    # Fetch work items referenced in PRs but missing from sprint query
    existing_wi_ids = {wi.id for wi in work_items}
    pr_referenced_ids: set[int] = set()
    for pr in all_prs:
        pr_referenced_ids.update(pr.extract_work_item_ids())
    missing_ids = sorted(pr_referenced_ids - existing_wi_ids)
    if missing_ids:
        print(f"Fetching {len(missing_ids)} PR-referenced work items not in sprint query...")
        extra_items = ado_client.get_work_items_by_ids(missing_ids)
        # Only keep items assigned to team members
        extra_items = filter_work_items_to_team(extra_items, team_identities)
        if extra_items:
            print(f"  Added {len(extra_items)} work items from PR references")
            work_items.extend(extra_items)

    # Calculate metrics
    metrics = {
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
    write_sprint_report(metrics, output_path)
    print(f"Report written to {output_path}")


def main():
    args = parse_args()
    run(config_path=args.config, output_dir=args.output_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
