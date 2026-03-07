"""Tests for sprint_metrics.metrics.pr_cycle_time — Step 7 TDD."""
from datetime import UTC, datetime

import pytest

from sprint_metrics.metrics.pr_cycle_time import calculate_pr_cycle_times
from tests.conftest import make_pull_request


class TestCalculatePrCycleTimes:
    def test_basic_pr_cycle_times(self):
        prs = [
            make_pull_request(
                number=1,
                author="jane",
                created_at=datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC),
                merged_at=datetime(2026, 3, 2, 10, 0, 0, tzinfo=UTC),
            ),
            make_pull_request(
                number=2,
                author="jane",
                created_at=datetime(2026, 3, 3, 8, 0, 0, tzinfo=UTC),
                merged_at=datetime(2026, 3, 3, 20, 0, 0, tzinfo=UTC),
            ),
        ]
        result = calculate_pr_cycle_times(prs)

        # PR1=24h, PR2=12h, avg=18h
        assert result["team"]["average_hours"] == pytest.approx(18.0)

    def test_per_person(self):
        prs = [
            make_pull_request(
                number=1,
                author="jane",
                created_at=datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC),
                merged_at=datetime(2026, 3, 2, 10, 0, 0, tzinfo=UTC),
            ),
            make_pull_request(
                number=2,
                author="john",
                created_at=datetime(2026, 3, 1, 8, 0, 0, tzinfo=UTC),
                merged_at=datetime(2026, 3, 1, 14, 0, 0, tzinfo=UTC),
            ),
        ]
        result = calculate_pr_cycle_times(prs)

        assert result["individual"]["jane"]["average_hours"] == pytest.approx(24.0)
        assert result["individual"]["john"]["average_hours"] == pytest.approx(6.0)

    def test_excludes_unmerged(self):
        prs = [
            make_pull_request(number=1, merged_at=datetime(2026, 3, 2, 10, 0, 0, tzinfo=UTC)),
            make_pull_request(number=2, merged_at=None),
        ]
        result = calculate_pr_cycle_times(prs)

        assert result["team"]["count"] == 1

    def test_empty(self):
        result = calculate_pr_cycle_times([])

        assert result["team"]["average_hours"] == 0.0
        assert result["team"]["count"] == 0
        assert result["individual"] == {}
