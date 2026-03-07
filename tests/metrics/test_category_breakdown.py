"""Tests for sprint_metrics.metrics.category_breakdown — Step 9 TDD."""
import pytest

from sprint_metrics.metrics.category_breakdown import calculate_category_breakdown
from tests.conftest import make_work_item


class TestCalculateCategoryBreakdown:
    def test_basic_breakdown(self):
        items = [
            make_work_item(id_=1, category="strategic", story_points=5.0),
            make_work_item(id_=2, category="strategic", story_points=3.0),
            make_work_item(id_=3, category="defects", story_points=2.0),
            make_work_item(id_=4, category="tech_health", story_points=8.0),
        ]
        result = calculate_category_breakdown(items, ["strategic", "tech_health", "defects"])

        assert result["team"]["strategic"]["points"] == 8.0
        assert result["team"]["strategic"]["count"] == 2
        assert result["team"]["defects"]["points"] == 2.0
        assert result["team"]["tech_health"]["points"] == 8.0

    def test_per_person(self):
        items = [
            make_work_item(id_=1, assigned_to="jane", category="strategic", story_points=5.0),
            make_work_item(id_=2, assigned_to="jane", category="defects", story_points=3.0),
            make_work_item(id_=3, assigned_to="john", category="strategic", story_points=8.0),
        ]
        result = calculate_category_breakdown(items, ["strategic", "defects"])

        assert result["individual"]["jane"]["strategic"]["points"] == 5.0
        assert result["individual"]["jane"]["defects"]["points"] == 3.0
        assert result["individual"]["john"]["strategic"]["points"] == 8.0

    def test_uncategorized(self):
        items = [
            make_work_item(id_=1, category=None, story_points=5.0),
            make_work_item(id_=2, category="unknown_cat", story_points=3.0),
        ]
        result = calculate_category_breakdown(items, ["strategic", "defects"])

        assert result["team"]["other"]["points"] == 8.0
        assert result["team"]["other"]["count"] == 2

    def test_empty(self):
        result = calculate_category_breakdown([], ["strategic", "defects"])

        assert result["team"]["strategic"]["points"] == 0.0
        assert result["team"]["strategic"]["count"] == 0
        assert result["individual"] == {}

    def test_none_story_points_treated_as_zero(self):
        items = [
            make_work_item(id_=1, category="strategic", story_points=None),
        ]
        result = calculate_category_breakdown(items, ["strategic"])

        assert result["team"]["strategic"]["points"] == 0.0
        assert result["team"]["strategic"]["count"] == 1
