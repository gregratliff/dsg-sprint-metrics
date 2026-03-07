"""Tests for sprint_metrics.reports.csv_writer — Step 10 TDD."""
import csv
import os

import pytest

from sprint_metrics.reports.csv_writer import write_sprint_report


@pytest.fixture
def sample_metrics():
    return {
        "sprint_name": "Sprint 10",
        "velocity": {
            "team": {"planned_points": 30.0, "delivered_points": 25.0, "delivery_rate": 0.833},
            "individual": {
                "jane": {"planned_points": 18.0, "delivered_points": 15.0},
                "john": {"planned_points": 12.0, "delivered_points": 10.0},
            },
        },
        "cycle_time": {
            "team": {"average_days": 3.5, "median_days": 3.0, "count": 8},
            "individual": {
                "jane": {"average_days": 3.0, "median_days": 2.5, "count": 5},
                "john": {"average_days": 4.25, "median_days": 4.0, "count": 3},
            },
        },
        "pr_cycle_time": {
            "team": {"average_hours": 18.0, "median_hours": 16.0, "count": 10},
            "individual": {
                "jane": {"average_hours": 14.0, "median_hours": 12.0, "count": 6},
                "john": {"average_hours": 24.0, "median_hours": 22.0, "count": 4},
            },
        },
        "rework": {
            "team": {"rework_count": 3, "rework_points": 8.0, "total_count": 12, "rework_rate": 0.25},
            "individual": {
                "jane": {"rework_count": 1, "rework_points": 3.0, "total_count": 7},
                "john": {"rework_count": 2, "rework_points": 5.0, "total_count": 5},
            },
        },
        "categories": {
            "team": {
                "strategic": {"points": 15.0, "count": 4},
                "tech_health": {"points": 8.0, "count": 3},
                "defects": {"points": 7.0, "count": 5},
                "other": {"points": 0.0, "count": 0},
            },
            "individual": {
                "jane": {
                    "strategic": {"points": 10.0, "count": 3},
                    "tech_health": {"points": 5.0, "count": 2},
                    "defects": {"points": 3.0, "count": 2},
                    "other": {"points": 0.0, "count": 0},
                },
                "john": {
                    "strategic": {"points": 5.0, "count": 1},
                    "tech_health": {"points": 3.0, "count": 1},
                    "defects": {"points": 4.0, "count": 3},
                    "other": {"points": 0.0, "count": 0},
                },
            },
        },
    }


class TestWriteSprintReport:
    def test_creates_file(self, tmp_path, sample_metrics):
        output = str(tmp_path / "report.csv")
        write_sprint_report(sample_metrics, output)

        assert os.path.exists(output)

    def test_file_has_content(self, tmp_path, sample_metrics):
        output = str(tmp_path / "report.csv")
        write_sprint_report(sample_metrics, output)

        with open(output) as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) > 1  # header + data rows

    def test_summary_has_team_row(self, tmp_path, sample_metrics):
        output = str(tmp_path / "report.csv")
        write_sprint_report(sample_metrics, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        team_rows = [r for r in rows if r["member"] == "TEAM"]
        assert len(team_rows) == 1

    def test_summary_has_individual_rows(self, tmp_path, sample_metrics):
        output = str(tmp_path / "report.csv")
        write_sprint_report(sample_metrics, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        members = {r["member"] for r in rows}
        assert "jane" in members
        assert "john" in members

    def test_velocity_columns(self, tmp_path, sample_metrics):
        output = str(tmp_path / "report.csv")
        write_sprint_report(sample_metrics, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        team_row = [r for r in rows if r["member"] == "TEAM"][0]
        assert team_row["planned_points"] == "30.0"
        assert team_row["delivered_points"] == "25.0"

    def test_cycle_time_columns(self, tmp_path, sample_metrics):
        output = str(tmp_path / "report.csv")
        write_sprint_report(sample_metrics, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        team_row = [r for r in rows if r["member"] == "TEAM"][0]
        assert team_row["avg_cycle_time_days"] == "3.5"
        assert team_row["avg_pr_cycle_time_hours"] == "18.0"

    def test_rework_columns(self, tmp_path, sample_metrics):
        output = str(tmp_path / "report.csv")
        write_sprint_report(sample_metrics, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        team_row = [r for r in rows if r["member"] == "TEAM"][0]
        assert team_row["rework_count"] == "3"
        assert team_row["rework_points"] == "8.0"

    def test_category_columns(self, tmp_path, sample_metrics):
        output = str(tmp_path / "report.csv")
        write_sprint_report(sample_metrics, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        team_row = [r for r in rows if r["member"] == "TEAM"][0]
        assert team_row["strategic_points"] == "15.0"
        assert team_row["defects_points"] == "7.0"

    def test_sprint_name_column(self, tmp_path, sample_metrics):
        output = str(tmp_path / "report.csv")
        write_sprint_report(sample_metrics, output)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert all(r["sprint"] == "Sprint 10" for r in rows)
