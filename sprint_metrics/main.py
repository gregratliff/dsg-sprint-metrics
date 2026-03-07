"""CLI entrypoint for sprint metrics collection."""
from __future__ import annotations

import argparse
import os
import sys

from sprint_metrics.config import load_config, Config
from sprint_metrics.clients.azure_devops_client import AzureDevOpsClient
from sprint_metrics.clients.github_client import GitHubClient
from sprint_metrics.metrics.velocity import calculate_velocity
from sprint_metrics.metrics.cycle_time import calculate_cycle_times
from sprint_metrics.metrics.pr_cycle_time import calculate_pr_cycle_times
from sprint_metrics.metrics.rework import calculate_rework
from sprint_metrics.metrics.category_breakdown import calculate_category_breakdown
from sprint_metrics.reports.csv_writer import write_sprint_report


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
    work_items = ado_client.get_sprint_work_items(iteration_path)

    all_prs = []
    team_usernames = [m.github_username for m in cfg.team_members]
    for repo_name in cfg.github.repos:
        repo_full = f"{cfg.github.org}/{repo_name}"
        prs = gh_client.get_pull_requests(
            repo=repo_full,
            start_date=cfg.sprint.start_date,
            end_date=cfg.sprint.end_date,
            team_usernames=team_usernames,
        )
        all_prs.extend(prs)

    # Calculate metrics
    metrics = {
        "sprint_name": cfg.sprint.name,
        "velocity": calculate_velocity(work_items),
        "cycle_time": calculate_cycle_times(work_items),
        "pr_cycle_time": calculate_pr_cycle_times(all_prs),
        "rework": calculate_rework(work_items, cfg.azure_devops.rework_labels),
        "categories": calculate_category_breakdown(work_items, cfg.categories),
    }

    # Write report
    safe_name = cfg.sprint.name.replace(" ", "_")
    output_path = os.path.join(output_dir, f"{safe_name}_report.csv")
    write_sprint_report(metrics, output_path)
    print(f"Report written to {output_path}")


def main():
    args = parse_args()
    run(config_path=args.config, output_dir=args.output_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
