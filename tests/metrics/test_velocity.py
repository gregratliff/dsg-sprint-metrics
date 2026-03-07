"""Tests for sprint_metrics.metrics.velocity — Step 5 TDD."""
from datetime import datetime, timezone

import pytest

from sprint_metrics.metrics.velocity import calculate_velocity
from tests.conftest import make_work_item


class TestCalculateVelocity:
    def test_basic_velocity(self, sprint_info):
        items = [
            make_work_item(id_=1, assigned_to="jane", story_points=5.0, state="Closed"),
            make_work_item(id_=2, assigned_to="jane", story_points=3.0, state="Active"),
            make_work_item(id_=3, assigned_to="john", story_points=8.0, state="Closed"),
        ]
        result = calculate_velocity(items)

        assert result["team"]["planned_points"] == 16.0
        assert result["team"]["delivered_points"] == 13.0

    def test_per_person_velocity(self, sprint_info):
        items = [
            make_work_item(id_=1, assigned_to="jane", story_points=5.0, state="Closed"),
            make_work_item(id_=2, assigned_to="jane", story_points=3.0, state="Active"),
            make_work_item(id_=3, assigned_to="john", story_points=8.0, state="Closed"),
        ]
        result = calculate_velocity(items)

        assert result["individual"]["jane"]["planned_points"] == 8.0
        assert result["individual"]["jane"]["delivered_points"] == 5.0
        assert result["individual"]["john"]["planned_points"] == 8.0
        assert result["individual"]["john"]["delivered_points"] == 8.0

    def test_no_story_points_excluded(self):
        items = [
            make_work_item(id_=1, story_points=None, state="Closed"),
            make_work_item(id_=2, story_points=0.0, state="Closed"),
            make_work_item(id_=3, story_points=5.0, state="Closed"),
        ]
        result = calculate_velocity(items)

        assert result["team"]["planned_points"] == 5.0
        assert result["team"]["delivered_points"] == 5.0

    def test_empty_items(self):
        result = calculate_velocity([])

        assert result["team"]["planned_points"] == 0.0
        assert result["team"]["delivered_points"] == 0.0
        assert result["individual"] == {}

    def test_delivery_rate(self):
        items = [
            make_work_item(id_=1, story_points=10.0, state="Closed"),
            make_work_item(id_=2, story_points=5.0, state="Active"),
        ]
        result = calculate_velocity(items)

        assert result["team"]["delivery_rate"] == pytest.approx(10.0 / 15.0)

    def test_delivery_rate_zero_planned(self):
        result = calculate_velocity([])
        assert result["team"]["delivery_rate"] == 0.0
