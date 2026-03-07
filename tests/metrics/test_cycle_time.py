"""Tests for sprint_metrics.metrics.cycle_time — Step 6 TDD."""
from datetime import datetime, timezone

import pytest

from sprint_metrics.metrics.cycle_time import calculate_cycle_times
from tests.conftest import make_work_item


class TestCalculateCycleTimes:
    def test_basic_cycle_times(self):
        items = [
            make_work_item(
                id_=1,
                assigned_to="jane",
                activated_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
                closed_date=datetime(2026, 3, 4, tzinfo=timezone.utc),
            ),
            make_work_item(
                id_=2,
                assigned_to="jane",
                activated_date=datetime(2026, 3, 2, tzinfo=timezone.utc),
                closed_date=datetime(2026, 3, 6, tzinfo=timezone.utc),
            ),
        ]
        result = calculate_cycle_times(items)

        assert result["team"]["average_days"] == pytest.approx(3.5)
        assert result["team"]["median_days"] == pytest.approx(3.5)

    def test_per_person_averages(self):
        items = [
            make_work_item(
                id_=1,
                assigned_to="jane",
                activated_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
                closed_date=datetime(2026, 3, 3, tzinfo=timezone.utc),
            ),
            make_work_item(
                id_=2,
                assigned_to="john",
                activated_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
                closed_date=datetime(2026, 3, 5, tzinfo=timezone.utc),
            ),
        ]
        result = calculate_cycle_times(items)

        assert result["individual"]["jane"]["average_days"] == pytest.approx(2.0)
        assert result["individual"]["john"]["average_days"] == pytest.approx(4.0)

    def test_excludes_items_without_dates(self):
        items = [
            make_work_item(
                id_=1,
                assigned_to="jane",
                activated_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
                closed_date=datetime(2026, 3, 3, tzinfo=timezone.utc),
            ),
            make_work_item(id_=2, assigned_to="jane", activated_date=None, closed_date=None),
            make_work_item(
                id_=3,
                assigned_to="jane",
                activated_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
                closed_date=None,
            ),
        ]
        result = calculate_cycle_times(items)

        assert result["team"]["count"] == 1
        assert result["team"]["average_days"] == pytest.approx(2.0)

    def test_empty_items(self):
        result = calculate_cycle_times([])

        assert result["team"]["average_days"] == 0.0
        assert result["team"]["median_days"] == 0.0
        assert result["team"]["count"] == 0
        assert result["individual"] == {}
