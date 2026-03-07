"""Tests for sprint_metrics.main — Step 11 TDD (integration-style, all clients mocked)."""
import csv
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from sprint_metrics.main import run, parse_args
from sprint_metrics.models import WorkItem, PullRequest


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
            labels=[], iteration_path="myproject\\Sprint 10",
            activated_date=datetime(2026, 3, 2, tzinfo=timezone.utc),
            closed_date=datetime(2026, 3, 5, tzinfo=timezone.utc),
        ),
        WorkItem(
            id=2, title="Bug B", assigned_to="jane.smith@company.com",
            story_points=3.0, state="Closed", category="defects",
            labels=["rework"], iteration_path="myproject\\Sprint 10",
            activated_date=datetime(2026, 3, 3, tzinfo=timezone.utc),
            closed_date=datetime(2026, 3, 6, tzinfo=timezone.utc),
        ),
    ]


def _sample_prs():
    return [
        PullRequest(
            id=100, number=1, title="PR 1", author="janesmith",
            created_at=datetime(2026, 3, 2, 10, 0, 0, tzinfo=timezone.utc),
            merged_at=datetime(2026, 3, 3, 10, 0, 0, tzinfo=timezone.utc),
            closed_at=datetime(2026, 3, 3, 10, 0, 0, tzinfo=timezone.utc),
            repo="myorg/repo1", commit_messages=["AB#1 feature A"],
        ),
    ]


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


class TestRun:
    def test_full_pipeline(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = _sample_work_items()
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
        team_row = [r for r in rows if r["member"] == "TEAM"][0]
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
            'name: "26\\\\Q1 2026\\\\Sprint 26.2.2"',
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_with_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_ado = MagicMock()
        mock_ado.get_sprint_work_items.return_value = _sample_work_items()
        mock_gh = MagicMock()
        mock_gh.get_pull_requests.return_value = _sample_prs()

        with patch("sprint_metrics.main._create_ado_client", return_value=mock_ado), \
             patch("sprint_metrics.main._create_github_client", return_value=mock_gh), \
             patch.dict(os.environ, {"ADO_PAT": "fake", "GITHUB_PAT": "fake"}):
            run(config_path=str(cfg_file), output_dir=str(output_dir))

        report_path = output_dir / "26_Q1_2026_Sprint_26.2.2_report.csv"
        assert report_path.exists()

    def test_missing_pat_env_var_raises(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)

        with patch.dict(os.environ, {}, clear=True), \
             pytest.raises(SystemExit):
            run(config_path=str(cfg_file), output_dir=str(tmp_path))
