"""Tests for sprint_metrics.metrics.rework — Step 8 TDD."""
import pytest

from sprint_metrics.metrics.rework import calculate_rework
from tests.conftest import make_work_item


class TestCalculateRework:
    def test_basic_rework(self):
        items = [
            make_work_item(id_=1, assigned_to="jane", story_points=5.0, labels=["rework"]),
            make_work_item(id_=2, assigned_to="jane", story_points=3.0, labels=[]),
            make_work_item(id_=3, assigned_to="john", story_points=8.0, labels=["missed-ac"]),
        ]
        result = calculate_rework(items, rework_labels=["rework", "missed-ac"])

        assert result["team"]["rework_count"] == 2
        assert result["team"]["rework_points"] == 13.0
        assert result["team"]["total_count"] == 3

    def test_rework_rate(self):
        items = [
            make_work_item(id_=1, labels=["rework"]),
            make_work_item(id_=2, labels=[]),
            make_work_item(id_=3, labels=[]),
            make_work_item(id_=4, labels=["missed-ac"]),
        ]
        result = calculate_rework(items, rework_labels=["rework", "missed-ac"])

        assert result["team"]["rework_rate"] == pytest.approx(0.5)

    def test_case_insensitive(self):
        items = [
            make_work_item(id_=1, labels=["Rework"]),
            make_work_item(id_=2, labels=["MISSED-AC"]),
        ]
        result = calculate_rework(items, rework_labels=["rework", "missed-ac"])

        assert result["team"]["rework_count"] == 2

    def test_multiple_rework_labels_counted_once(self):
        items = [
            make_work_item(id_=1, labels=["rework", "missed-ac"]),
        ]
        result = calculate_rework(items, rework_labels=["rework", "missed-ac"])

        assert result["team"]["rework_count"] == 1

    def test_per_person(self):
        items = [
            make_work_item(id_=1, assigned_to="jane", labels=["rework"], story_points=5.0),
            make_work_item(id_=2, assigned_to="jane", labels=[], story_points=3.0),
            make_work_item(id_=3, assigned_to="john", labels=["rework"], story_points=2.0),
        ]
        result = calculate_rework(items, rework_labels=["rework"])

        assert result["individual"]["jane"]["rework_count"] == 1
        assert result["individual"]["jane"]["rework_points"] == 5.0
        assert result["individual"]["john"]["rework_count"] == 1

    def test_zero_rework(self):
        items = [
            make_work_item(id_=1, labels=[]),
            make_work_item(id_=2, labels=["other-tag"]),
        ]
        result = calculate_rework(items, rework_labels=["rework"])

        assert result["team"]["rework_count"] == 0
        assert result["team"]["rework_rate"] == 0.0

    def test_empty(self):
        result = calculate_rework([], rework_labels=["rework"])

        assert result["team"]["rework_count"] == 0
        assert result["team"]["rework_rate"] == 0.0
        assert result["individual"] == {}
