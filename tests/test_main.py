"""Tests for sprint_metrics.main — Step 11 TDD (integration-style, all clients mocked)."""
import csv
import logging
import os
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from sprint_metrics.main import (
    classify_sprint_scope,
    filter_excluded_prs,
    filter_work_items_to_team,
    normalize_metrics_identity,
    parse_args,
    run,
)
from sprint_metrics.models import PullRequest, ScopeStatus, WorkItem

VALID_YAML = """\
azure_devops:
  organization: "myorg"
  project: "myproject"
  pat_env_var: "ADO_PAT"
  category_field: "Custom.Category"
  rework_labels:
    - "rework"
    - "missed-ac"

github:
  org: "myorg"
  repos:
    - "repo1"
  pat_env_var: "GITHUB_PAT"

sprint:
  stem: "26\\\\Q1 2026"
  name: "Sprint 10"
  start_date: "2026-03-01"
  end_date: "2026-03-14"

team_members:
  - name: "Jane Smith"
    github_username: "janesmith"
    ado_identity: "jane.smith@company.com"

categories:
  - "strategic"
  - "defects"
"""


def _sample_work_items():
    return [
        WorkItem(
            id=1, title="Feature A", assigned_to="jane.smith@company.com",
            story_points=5.0, state="Closed", category="strategic",
            labels=[], iteration_path="myproject\\26\\Q1 2026\\Sprint 10",
            activated_date=datetime(2026, 3, 2, tzinfo=UTC),
            closed_date=datetime(2026, 3, 5, tzinfo=UTC),
        ),
        WorkItem(
            id=2, title="Bug B", assigned_to="jane.smith@company.com",
            story_points=3.0, state="Closed", category="defects",
            labels=["rework"], iteration_path="myproject\\26\\Q1 2026\\Sprint 10",
            activated_date=datetime(2026, 3, 3, tzinfo=UTC),
            closed_date=datetime(2026, 3, 6, tzinfo=UTC),
        ),
    ]


def _sample_prs():
    return [
        PullRequest(
            id=100, number=1, title="PR 1", author="janesmith",
            created_at=datetime(2026, 3, 2, 10, 0, 0, tzinfo=UTC),
            merged_at=datetime(2026, 3, 3, 10, 0, 0, tzinfo=UTC),
            closed_at=datetime(2026, 3, 3, 10, 0, 0, tzinfo=UTC),
            repo="myorg/repo1", commit_messages=["AB#1 feature A"],
        ),
    ]


class TestFilterExcludedPrs:
    def test_excludes_matching_titles(self):
        patterns = ["^(production|pentest|master) deploy", "^develop -> master"]
        prs = [
            PullRequest(id=1, number=1, title="production deploy 2026-02-26",
                        author="a", created_at=datetime(2026, 3, 1, tzinfo=UTC),
                        merged_at=None, closed_at=None, repo="r"),
            PullRequest(id=2, number=2, title="develop -> master 2026-02-26",
                        author="a", created_at=datetime(2026, 3, 1, tzinfo=UTC),
                        merged_at=None, closed_at=None, repo="r"),
            PullRequest(id=3, number=3, title="1422900 RouteDetails: Stop Status Code Badge",
                        author="a", created_at=datetime(2026, 3, 1, tzinfo=UTC),
                        merged_at=None, closed_at=None, repo="r"),
        ]
        result = filter_excluded_prs(prs, patterns)
        assert len(result) == 1
        assert result[0].id == 3

    def test_empty_patterns_keeps_all(self):
        prs = [
            PullRequest(id=1, number=1, title="production deploy",
                        author="a", created_at=datetime(2026, 3, 1, tzinfo=UTC),
                        merged_at=None, closed_at=None, repo="r"),
        ]
        result = filter_excluded_prs(prs, [])
        assert len(result) == 1

    def test_case_insensitive_matching(self):
        patterns = ["^production deploy"]
        prs = [
            PullRequest(id=1, number=1, title="Production Deploy 2026-02-26",
                        author="a", created_at=datetime(2026, 3, 1, tzinfo=UTC),
                        merged_at=None, closed_at=None, repo="r"),
        ]
        result = filter_excluded_prs(prs, patterns)
        assert len(result) == 0

    def test_excludes_revert_of_excluded_pr(self):
        """A Revert of an excluded PR should also be excluded."""
        patterns = ["^develop -> master"]
        prs = [
            PullRequest(id=1, number=1, title='Revert "develop -> master 2026-03-02 2316"',
                        author="a", created_at=datetime(2026, 3, 1, tzinfo=UTC),
                        merged_at=None, closed_at=None, repo="r"),
        ]
        result = filter_excluded_prs(prs, patterns)
        assert len(result) == 0

    def test_excludes_nested_revert_of_excluded_pr(self):
        """A Revert of a Revert of an excluded PR should also be excluded."""
        patterns = ["^develop -> master"]
        prs = [
            PullRequest(id=1, number=1,
                        title='Revert "Revert "develop -> master 2026-03-02 2316""',
                        author="a", created_at=datetime(2026, 3, 1, tzinfo=UTC),
                        merged_at=None, closed_at=None, repo="r"),
        ]
        result = filter_excluded_prs(prs, patterns)
        assert len(result) == 0

    def test_revert_of_non_excluded_pr_kept(self):
        """A Revert of a normal PR should NOT be excluded."""
        patterns = ["^develop -> master"]
        prs = [
            PullRequest(id=1, number=1, title='Revert "Fix login bug #1234"',
                        author="a", created_at=datetime(2026, 3, 1, tzinfo=UTC),
                        merged_at=None, closed_at=None, repo="r"),
        ]
        result = filter_excluded_prs(prs, patterns)
        assert len(result) == 1

    def test_excludes_revert_with_feature_deploy_pattern(self):
        """Revert of a PR matching a non-anchored pattern should be excluded."""
        patterns = ["feature/deploy"]
        prs = [
            PullRequest(id=1, number=1, title='Revert "feature/deploy hotfix"',
                        author="a", created_at=datetime(2026, 3, 1, tzinfo=UTC),
                        merged_at=None, closed_at=None, repo="r"),
        ]
        result = filter_excluded_prs(prs, patterns)
        assert len(result) == 0


class TestNormalizeMetricsIdentity:
    def _make_config_members(self):
        from sprint_metrics.config import TeamMember
        return [
            TeamMember(name="Jane Smith", github_username="janesmith",
                       ado_identity="jane.smith@company.com"),
            TeamMember(name="John Doe", github_username="johndoe",
                       ado_identity="john.doe@company.com"),
        ]

    def test_remaps_ado_and_github_keys_to_display_name(self):
        members = self._make_config_members()
        metrics = {
            "sprint_name": "Sprint 10",
            "velocity": {
                "team": {"planned_points": 8},
                "individual": {
                    "jane.smith@company.com": {"planned_points": 5},
                    "john.doe@company.com": {"planned_points": 3},
                },
            },
            "pr_cycle_time": {
                "team": {"average_hours": 24},
                "individual": {
                    "janesmith": {"average_hours": 20},
                    "johndoe": {"average_hours": 28},
                },
            },
            "cycle_time": {"team": {}, "individual": {}},
            "rework": {"team": {}, "individual": {}},
            "categories": {"team": {}, "individual": {}},
        }
        result = normalize_metrics_identity(metrics, members)

        # velocity individual keys should now be display names
        assert "Jane Smith" in result["velocity"]["individual"]
        assert "jane.smith@company.com" not in result["velocity"]["individual"]

        # pr_cycle_time individual keys should now be display names
        assert "Jane Smith" in result["pr_cycle_time"]["individual"]
        assert "janesmith" not in result["pr_cycle_time"]["individual"]

        # member_info should map display name -> identity details
        assert result["member_info"]["Jane Smith"]["ado_identity"] == "jane.smith@company.com"
        assert result["member_info"]["Jane Smith"]["github_username"] == "janesmith"

    def test_merges_ado_and_github_data_under_same_key(self):
        members = self._make_config_members()
        metrics = {
            "sprint_name": "Sprint 10",
            "velocity": {
                "team": {},
                "individual": {"jane.smith@company.com": {"planned_points": 5}},
            },
            "pr_cycle_time": {
                "team": {},
                "individual": {"janesmith": {"average_hours": 20}},
            },
            "cycle_time": {"team": {}, "individual": {}},
            "rework": {"team": {}, "individual": {}},
            "categories": {"team": {}, "individual": {}},
        }
        result = normalize_metrics_identity(metrics, members)

        # Both velocity AND pr_cycle_time should have Jane Smith
        assert "Jane Smith" in result["velocity"]["individual"]
        assert "Jane Smith" in result["pr_cycle_time"]["individual"]


class TestFilterWorkItemsToTeam:
    def test_excludes_non_team_members(self):
        team_identities = {"jane.smith@company.com"}
        items = [
            WorkItem(id=1, title="A", assigned_to="jane.smith@company.com",
                     story_points=5.0, state="Closed", category="strategic",
                     labels=[], iteration_path="p\\Sprint 10",
                     activated_date=datetime(2026, 3, 1, tzinfo=UTC),
                     closed_date=datetime(2026, 3, 3, tzinfo=UTC)),
            WorkItem(id=2, title="B", assigned_to="other.person@company.com",
                     story_points=3.0, state="Closed", category="defects",
                     labels=[], iteration_path="p\\Sprint 10",
                     activated_date=datetime(2026, 3, 1, tzinfo=UTC),
                     closed_date=datetime(2026, 3, 3, tzinfo=UTC)),
        ]
        result = filter_work_items_to_team(items, team_identities)
        assert len(result) == 1
        assert result[0].assigned_to == "jane.smith@company.com"

    def test_empty_team_returns_empty(self):
        items = [
            WorkItem(id=1, title="A", assigned_to="anyone@company.com",
                     story_points=5.0, state="Closed", category="strategic",
                     labels=[], iteration_path="p\\Sprint 10",
                     activated_date=None, closed_date=None),
        ]
        result = filter_work_items_to_team(items, set())
        assert len(result) == 0


class TestParseArgs:
    def test_required_config(self):
        args = parse_args(["--config", "config.yaml"])
        assert args.config == "config.yaml"

    def test_output_dir_default(self):
        args = parse_args(["--config", "config.yaml"])
        assert args.output_dir == "."

    def test_output_dir_custom(self):
        args = parse_args(["--config", "config.yaml", "--output-dir", "/tmp/out"])
        assert args.output_dir == "/tmp/out"

    def test_dry_run(self):
        args = parse_args(["--config", "config.yaml", "--dry-run"])
        assert args.dry_run is True

    def test_sprint_name_option(self):
        args = parse_args(["--config", "config.yaml", "--sprint-name", "Sprint 26.3.1"])
        assert args.sprint_name == "Sprint 26.3.1"

    def test_sprint_name_default_none(self):
        args = parse_args(["--config", "config.yaml"])
        assert args.sprint_name is None


class TestRun:
    def test_full_pipeline(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = _sample_work_items()
        mock_ado.get_sprint_work_items_asof.return_value = _sample_work_items()
        mock_gh = MagicMock()
        mock_gh.get_pull_requests.return_value = _sample_prs()

        with patch("sprint_metrics.main._create_ado_client", return_value=mock_ado), \
             patch("sprint_metrics.main._create_github_client", return_value=mock_gh), \
             patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}):

            run(config_path=str(cfg_file), output_dir=str(output_dir))

        report_path = output_dir / "Sprint_10_report.csv"
        assert report_path.exists()

        with open(report_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) >= 1  # at least team row
        team_row = next(r for r in rows if r["member"] == "TEAM")
        assert team_row["sprint"] == "Sprint 10"
        assert float(team_row["planned_points"]) == 8.0
        assert float(team_row["delivered_points"]) == 8.0

    def test_dry_run_does_not_call_apis(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)

        with patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}):
            # dry_run should validate config but not call APIs
            run(config_path=str(cfg_file), output_dir=str(tmp_path), dry_run=True)

        # No CSV should be created in dry run
        csv_files = list(tmp_path.glob("*.csv"))
        assert len(csv_files) == 0

    def test_sprint_name_with_backslashes_produces_flat_filename(self, tmp_path):
        yaml_with_path = VALID_YAML.replace(
            'name: "Sprint 10"',
            'name: "Sprint 26.2.2"',
        ).replace(
            'stem: "26\\\\Q1 2026"',
            'stem: "26\\\\Q1 2026"',
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_with_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = _sample_work_items()
        mock_ado.get_sprint_work_items_asof.return_value = _sample_work_items()
        mock_gh = MagicMock()
        mock_gh.get_pull_requests.return_value = _sample_prs()

        with patch("sprint_metrics.main._create_ado_client", return_value=mock_ado), \
             patch("sprint_metrics.main._create_github_client", return_value=mock_gh), \
             patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}):
            run(config_path=str(cfg_file), output_dir=str(output_dir))

        report_path = output_dir / "Sprint_26.2.2_report.csv"
        assert report_path.exists()

    def test_combined_identity_single_row_per_member(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = _sample_work_items()
        mock_ado.get_sprint_work_items_asof.return_value = _sample_work_items()
        mock_gh = MagicMock()
        mock_gh.get_pull_requests.return_value = _sample_prs()

        with patch("sprint_metrics.main._create_ado_client", return_value=mock_ado), \
             patch("sprint_metrics.main._create_github_client", return_value=mock_gh), \
             patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}):
            run(config_path=str(cfg_file), output_dir=str(output_dir))

        report_path = output_dir / "Sprint_10_report.csv"
        with open(report_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have TEAM row + 1 member row (not separate ADO + GitHub rows)
        non_team_rows = [r for r in rows if r["member"] != "TEAM"]
        assert len(non_team_rows) == 1
        jane_row = non_team_rows[0]
        assert jane_row["member"] == "Jane Smith"
        assert jane_row["ado_identity"] == "jane.smith@company.com"
        assert jane_row["github_username"] == "janesmith"
        # Should have both ADO metrics and PR metrics
        assert float(jane_row["planned_points"]) == 8.0
        assert int(jane_row["pr_count"]) == 1

    def test_non_team_work_items_excluded_from_report(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        other_team_item = WorkItem(
            id=99, title="Other Team Task",
            assigned_to="other.person@company.com",
            story_points=10.0, state="Closed", category="strategic",
            labels=[], iteration_path="myproject\\26\\Q1 2026\\Sprint 10",
            activated_date=datetime(2026, 3, 2, tzinfo=UTC),
            closed_date=datetime(2026, 3, 5, tzinfo=UTC),
        )
        items = [*_sample_work_items(), other_team_item]

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = items
        mock_ado.get_sprint_work_items_asof.return_value = items
        mock_gh = MagicMock()
        mock_gh.get_pull_requests.return_value = _sample_prs()

        with patch("sprint_metrics.main._create_ado_client", return_value=mock_ado), \
             patch("sprint_metrics.main._create_github_client", return_value=mock_gh), \
             patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}):
            run(config_path=str(cfg_file), output_dir=str(output_dir))

        report_path = output_dir / "Sprint_10_report.csv"
        with open(report_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        members = [r["member"] for r in rows]
        # other.person should NOT appear
        assert "other.person@company.com" not in members
        # team total should be 8 points (not 18)
        team_row = next(r for r in rows if r["member"] == "TEAM")
        assert float(team_row["planned_points"]) == 8.0

    def test_deployment_prs_excluded_from_report(self, tmp_path):
        yaml_with_patterns = VALID_YAML.replace(
            '  pat_env_var: "GITHUB_PAT"',
            '  pat_env_var: "GITHUB_PAT"\n'
            '  pr_exclude_patterns:\n'
            '    - "^(production|pentest|master) deploy"\n'
            '    - "^develop -> master"',
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_with_patterns)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        deploy_pr = PullRequest(
            id=200, number=2, title="production deploy 2026-02-26-1956",
            author="janesmith",
            created_at=datetime(2026, 3, 10, 10, 0, 0, tzinfo=UTC),
            merged_at=datetime(2026, 3, 10, 10, 5, 0, tzinfo=UTC),
            closed_at=datetime(2026, 3, 10, 10, 5, 0, tzinfo=UTC),
            repo="myorg/repo1", commit_messages=[],
        )
        prs_with_deploy = [*_sample_prs(), deploy_pr]

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = _sample_work_items()
        mock_ado.get_sprint_work_items_asof.return_value = _sample_work_items()
        mock_gh = MagicMock()
        mock_gh.get_pull_requests.return_value = prs_with_deploy

        with patch("sprint_metrics.main._create_ado_client", return_value=mock_ado), \
             patch("sprint_metrics.main._create_github_client", return_value=mock_gh), \
             patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}):
            run(config_path=str(cfg_file), output_dir=str(output_dir))

        report_path = output_dir / "Sprint_10_report.csv"
        with open(report_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        team_row = next(r for r in rows if r["member"] == "TEAM")
        # Only 1 PR should be counted (deploy PR excluded)
        assert int(team_row["pr_count"]) == 1

    def test_single_repo_failure_continues_with_other_repos(self, tmp_path):
        """If one repo fails, PRs from other repos are still collected."""
        yaml_two_repos = VALID_YAML.replace(
            '  repos:\n    - "repo1"',
            '  repos:\n    - "repo1"\n    - "repo2"',
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_two_repos)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = _sample_work_items()
        mock_ado.get_sprint_work_items_asof.return_value = _sample_work_items()

        mock_gh = MagicMock()
        # First repo fails, second succeeds
        def side_effect(repo, **kwargs):
            if "repo1" in repo:
                raise RuntimeError("Failed to access repository 'myorg/repo1'")
            return _sample_prs()
        mock_gh.get_pull_requests.side_effect = side_effect

        with patch("sprint_metrics.main._create_ado_client", return_value=mock_ado), \
             patch("sprint_metrics.main._create_github_client", return_value=mock_gh), \
             patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}):
            run(config_path=str(cfg_file), output_dir=str(output_dir))

        report_path = output_dir / "Sprint_10_report.csv"
        assert report_path.exists()
        with open(report_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        team_row = next(r for r in rows if r["member"] == "TEAM")
        assert int(team_row["pr_count"]) == 1  # Only from repo2

    def test_invalid_pr_work_item_ids_continue(self, tmp_path, caplog):
        """Pipeline completes even when PR references non-existent work items.

        Warning should include the offending PR number and author.
        """
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = _sample_work_items()
        mock_ado.get_sprint_work_items_asof.return_value = _sample_work_items()
        # get_work_items_by_ids returns empty (all invalid IDs were skipped)
        mock_ado.get_work_items_by_ids.return_value = []

        # PR references a non-existent work item
        bad_ref_pr = PullRequest(
            id=999, number=99, title="12345 bad ref PR", author="janesmith",
            created_at=datetime(2026, 3, 2, 10, 0, 0, tzinfo=UTC),
            merged_at=datetime(2026, 3, 3, 10, 0, 0, tzinfo=UTC),
            closed_at=datetime(2026, 3, 3, 10, 0, 0, tzinfo=UTC),
            repo="myorg/repo1", commit_messages=["AB#56789 also fake"],
        )
        mock_gh = MagicMock()
        mock_gh.get_pull_requests.return_value = [*_sample_prs(), bad_ref_pr]

        with patch("sprint_metrics.main._create_ado_client", return_value=mock_ado), \
             patch("sprint_metrics.main._create_github_client", return_value=mock_gh), \
             patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}), \
             caplog.at_level(logging.WARNING):
            run(config_path=str(cfg_file), output_dir=str(output_dir))

        report_path = output_dir / "Sprint_10_report.csv"
        assert report_path.exists()

        # Warning should mention the unfound work item IDs with PR context
        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        # Work item 12345 referenced by PR #99 (janesmith)
        assert any("12345" in w and "#99" in w and "janesmith" in w for w in warnings), \
            f"Expected warning about work item 12345 from PR #99 by janesmith, got: {warnings}"
        # Work item 56789 referenced by PR #99 (janesmith)
        assert any("56789" in w and "#99" in w and "janesmith" in w for w in warnings), \
            f"Expected warning about work item 56789 from PR #99 by janesmith, got: {warnings}"

    def test_pr_with_no_work_item_reference_warns(self, tmp_path, caplog):
        """PRs with no work item ID in title, body, or commits should warn."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = _sample_work_items()
        mock_ado.get_sprint_work_items_asof.return_value = _sample_work_items()

        # PR with no work item reference at all
        no_ref_pr = PullRequest(
            id=800, number=55, title="Fix flaky test", author="johndoe",
            created_at=datetime(2026, 3, 2, 10, 0, 0, tzinfo=UTC),
            merged_at=datetime(2026, 3, 3, 10, 0, 0, tzinfo=UTC),
            closed_at=datetime(2026, 3, 3, 10, 0, 0, tzinfo=UTC),
            repo="myorg/repo1", body="", commit_messages=["fix the test"],
        )
        mock_gh = MagicMock()
        mock_gh.get_pull_requests.return_value = [*_sample_prs(), no_ref_pr]

        with patch("sprint_metrics.main._create_ado_client", return_value=mock_ado), \
             patch("sprint_metrics.main._create_github_client", return_value=mock_gh), \
             patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}), \
             caplog.at_level(logging.WARNING):
            run(config_path=str(cfg_file), output_dir=str(output_dir))

        report_path = output_dir / "Sprint_10_report.csv"
        assert report_path.exists()

        warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("#55" in w and "johndoe" in w and "no work item" in w.lower() for w in warnings), \
            f"Expected warning about PR #55 by johndoe having no work item reference, got: {warnings}"

    def test_output_dir_not_found_raises_clear_error(self, tmp_path):
        """Non-existent output directory gives a clear error message."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = _sample_work_items()
        mock_ado.get_sprint_work_items_asof.return_value = _sample_work_items()
        mock_gh = MagicMock()
        mock_gh.get_pull_requests.return_value = _sample_prs()

        with patch("sprint_metrics.main._create_ado_client", return_value=mock_ado), \
             patch("sprint_metrics.main._create_github_client", return_value=mock_gh), \
             patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}), \
             pytest.raises(RuntimeError, match="Failed to write report"):
            run(config_path=str(cfg_file), output_dir="/nonexistent/path/does/not/exist")

    def test_sprint_name_cli_overrides_config(self, tmp_path):
        """--sprint-name CLI option overrides sprint.name from config."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = _sample_work_items()
        mock_ado.get_sprint_work_items_asof.return_value = _sample_work_items()
        mock_gh = MagicMock()
        mock_gh.get_pull_requests.return_value = _sample_prs()

        with patch("sprint_metrics.main._create_ado_client", return_value=mock_ado), \
             patch("sprint_metrics.main._create_github_client", return_value=mock_gh), \
             patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}):
            run(config_path=str(cfg_file), output_dir=str(output_dir),
                sprint_name="Sprint 26.3.1")

        # Report filename should use the overridden name
        report_path = output_dir / "Sprint_26.3.1_report.csv"
        assert report_path.exists()

        with open(report_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        team_row = next(r for r in rows if r["member"] == "TEAM")
        assert team_row["sprint"] == "Sprint 26.3.1"

    def test_iteration_path_uses_stem_and_name(self, tmp_path):
        """Iteration path should be project\\stem\\name."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = _sample_work_items()
        mock_ado.get_sprint_work_items_asof.return_value = _sample_work_items()
        mock_gh = MagicMock()
        mock_gh.get_pull_requests.return_value = _sample_prs()

        with patch("sprint_metrics.main._create_ado_client", return_value=mock_ado), \
             patch("sprint_metrics.main._create_github_client", return_value=mock_gh), \
             patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}):
            run(config_path=str(cfg_file), output_dir=str(output_dir))

        # Verify iteration path passed to ADO client includes stem
        call_args = mock_ado.get_sprint_work_items_asof.call_args_list[0]
        iteration_path = call_args[0][0]
        assert iteration_path == "myproject\\26\\Q1 2026\\Sprint 10"

    def test_missing_pat_env_var_raises(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)

        with patch.dict(os.environ, {}, clear=True), \
             pytest.raises(SystemExit):
            run(config_path=str(cfg_file), output_dir=str(tmp_path))


class TestClassifySprintScope:
    def _make_wi(self, id_, state="Closed", story_points=3.0, assigned_to="jane"):
        return WorkItem(
            id=id_, title=f"Item {id_}", assigned_to=assigned_to,
            story_points=story_points, state=state, category="strategic",
            labels=[], activated_date=None, closed_date=None,
            iteration_path="P\\26\\Q1 2026\\Sprint 10",
        )

    def test_item_in_both_snapshots_is_committed(self):
        planned = [self._make_wi(1)]
        end = [self._make_wi(1)]
        result = classify_sprint_scope(planned, end)
        assert len(result) == 1
        assert result[0].scope_status == ScopeStatus.COMMITTED

    def test_item_only_in_planned_is_removed(self):
        planned = [self._make_wi(1)]
        end = []
        result = classify_sprint_scope(planned, end)
        assert len(result) == 1
        assert result[0].scope_status == ScopeStatus.REMOVED

    def test_item_only_in_end_is_added(self):
        planned = []
        end = [self._make_wi(2)]
        result = classify_sprint_scope(planned, end)
        assert len(result) == 1
        assert result[0].scope_status == ScopeStatus.ADDED_MID_SPRINT

    def test_mixed_classification(self):
        planned = [self._make_wi(1), self._make_wi(2)]
        end = [self._make_wi(2), self._make_wi(3)]
        result = classify_sprint_scope(planned, end)

        by_id = {wi.id: wi for wi in result}
        assert by_id[1].scope_status == ScopeStatus.REMOVED
        assert by_id[2].scope_status == ScopeStatus.COMMITTED
        assert by_id[3].scope_status == ScopeStatus.ADDED_MID_SPRINT

    def test_empty_inputs(self):
        assert classify_sprint_scope([], []) == []

    def test_committed_uses_end_of_sprint_data(self):
        """For items in both, use end-of-sprint data (more current state)."""
        planned = [self._make_wi(1, state="Active")]
        end = [self._make_wi(1, state="Closed")]
        result = classify_sprint_scope(planned, end)
        assert result[0].state == "Closed"

    def test_removed_item_moved_to_another_sprint_is_carried_over(self):
        """Item in planned but not end-of-sprint, currently in a different sprint iteration."""
        planned = [self._make_wi(1)]
        end = []
        # Current state shows item moved to Sprint 11
        current_wi = self._make_wi(1)
        current_wi.iteration_path = "P\\Sprint 11"
        current_items_by_id = {1: current_wi}
        result = classify_sprint_scope(
            planned, end,
            current_items_by_id=current_items_by_id,
            sprint_iteration_path="P\\26\\Q1 2026\\Sprint 10",
        )
        assert len(result) == 1
        assert result[0].scope_status == ScopeStatus.CARRIED_OVER

    def test_removed_item_moved_to_backlog_stays_removed(self):
        """Item moved to parent iteration (backlog) stays REMOVED."""
        planned = [self._make_wi(1)]
        end = []
        # Current state: item moved to project-level backlog (parent of sprint path)
        current_wi = self._make_wi(1)
        current_wi.iteration_path = "P"
        current_items_by_id = {1: current_wi}
        result = classify_sprint_scope(
            planned, end,
            current_items_by_id=current_items_by_id,
            sprint_iteration_path="P\\26\\Q1 2026\\Sprint 10",
        )
        assert len(result) == 1
        assert result[0].scope_status == ScopeStatus.REMOVED

    def test_removed_item_not_in_current_stays_removed(self):
        """Item not found in current lookup (deleted?) stays REMOVED."""
        planned = [self._make_wi(1)]
        end = []
        current_items_by_id = {}  # item not found
        result = classify_sprint_scope(
            planned, end,
            current_items_by_id=current_items_by_id,
            sprint_iteration_path="P\\26\\Q1 2026\\Sprint 10",
        )
        assert len(result) == 1
        assert result[0].scope_status == ScopeStatus.REMOVED

    def test_carried_over_uses_current_data(self):
        """Carried-over items should use current state data (not stale planning snapshot)."""
        planned = [self._make_wi(1, state="Active")]
        end = []
        current_wi = self._make_wi(1, state="Closed")
        current_wi.iteration_path = "P\\Sprint 11"
        current_items_by_id = {1: current_wi}
        result = classify_sprint_scope(
            planned, end,
            current_items_by_id=current_items_by_id,
            sprint_iteration_path="P\\26\\Q1 2026\\Sprint 10",
        )
        assert result[0].state == "Closed"
        assert result[0].scope_status == ScopeStatus.CARRIED_OVER

    def test_backward_compatible_without_current_items(self):
        """Without current_items_by_id, behaves like before (all removed stay REMOVED)."""
        planned = [self._make_wi(1)]
        end = []
        result = classify_sprint_scope(planned, end)
        assert result[0].scope_status == ScopeStatus.REMOVED

    def test_mixed_with_carryover(self):
        """Mixed scenario: committed, added, removed, and carried-over."""
        planned = [self._make_wi(1), self._make_wi(2), self._make_wi(3)]
        end = [self._make_wi(1), self._make_wi(4)]
        # Item 2 moved to next sprint, item 3 moved to backlog
        current_2 = self._make_wi(2)
        current_2.iteration_path = "P\\Sprint 11"
        current_3 = self._make_wi(3)
        current_3.iteration_path = "P"
        current_items_by_id = {2: current_2, 3: current_3}
        result = classify_sprint_scope(
            planned, end,
            current_items_by_id=current_items_by_id,
            sprint_iteration_path="P\\26\\Q1 2026\\Sprint 10",
        )
        by_id = {wi.id: wi for wi in result}
        assert by_id[1].scope_status == ScopeStatus.COMMITTED
        assert by_id[2].scope_status == ScopeStatus.CARRIED_OVER
        assert by_id[3].scope_status == ScopeStatus.REMOVED
        assert by_id[4].scope_status == ScopeStatus.ADDED_MID_SPRINT
