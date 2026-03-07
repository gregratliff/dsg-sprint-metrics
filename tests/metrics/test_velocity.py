"""Tests for sprint_metrics.metrics.velocity — Step 5 TDD."""
from datetime import datetime, timezone

import pytest

from sprint_metrics.metrics.velocity import calculate_velocity
from sprint_metrics.models import ScopeStatus
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

    def test_scope_aware_planned_excludes_added(self):
        """Items added mid-sprint don't count toward planned points."""
        items = [
            make_work_item(id_=1, story_points=5.0, state="Closed",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=2, story_points=3.0, state="Closed",
                           scope_status=ScopeStatus.ADDED_MID_SPRINT),
        ]
        result = calculate_velocity(items)

        assert result["team"]["planned_points"] == 5.0
        assert result["team"]["delivered_points"] == 8.0

    def test_removed_items_count_as_planned_not_delivered(self):
        """Items removed from sprint still count toward planned points."""
        items = [
            make_work_item(id_=1, story_points=5.0, state="Closed",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=2, story_points=3.0, state="Active",
                           scope_status=ScopeStatus.REMOVED),
        ]
        result = calculate_velocity(items)

        assert result["team"]["planned_points"] == 8.0
        assert result["team"]["delivered_points"] == 5.0

    def test_scope_change_metrics(self):
        """Scope change metrics track added and removed points."""
        items = [
            make_work_item(id_=1, story_points=5.0, state="Closed",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=2, story_points=3.0, state="Closed",
                           scope_status=ScopeStatus.ADDED_MID_SPRINT),
            make_work_item(id_=3, story_points=2.0, state="Active",
                           scope_status=ScopeStatus.REMOVED),
        ]
        result = calculate_velocity(items)

        assert result["team"]["scope_added_points"] == 3.0
        assert result["team"]["scope_removed_points"] == 2.0

    def test_carryover_metrics(self):
        """Carryover = non-closed items that are COMMITTED or ADDED."""
        items = [
            make_work_item(id_=1, story_points=5.0, state="Closed",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=2, story_points=3.0, state="Active",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=3, story_points=2.0, state="Active",
                           scope_status=ScopeStatus.ADDED_MID_SPRINT),
        ]
        result = calculate_velocity(items)

        assert result["team"]["carryover_points"] == 5.0
        # carryover_rate = carryover / planned. planned = 8 (committed: 5+3)
        assert result["team"]["carryover_rate"] == pytest.approx(5.0 / 8.0)

    def test_commitment_reliability(self):
        """commitment_reliability = closed COMMITTED / planned."""
        items = [
            make_work_item(id_=1, story_points=5.0, state="Closed",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=2, story_points=3.0, state="Active",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=3, story_points=2.0, state="Closed",
                           scope_status=ScopeStatus.ADDED_MID_SPRINT),
        ]
        result = calculate_velocity(items)

        # planned = 8 (committed items: 5+3), committed_delivered = 5
        assert result["team"]["commitment_reliability"] == pytest.approx(5.0 / 8.0)

    def test_carried_over_counts_as_planned(self):
        """CARRIED_OVER items count toward planned points (like REMOVED)."""
        items = [
            make_work_item(id_=1, story_points=5.0, state="Closed",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=2, story_points=3.0, state="Active",
                           scope_status=ScopeStatus.CARRIED_OVER),
        ]
        result = calculate_velocity(items)

        # planned = 5 (committed) + 3 (carried_over) = 8
        assert result["team"]["planned_points"] == 8.0

    def test_carried_over_counts_as_carryover_points(self):
        """CARRIED_OVER items count toward carryover_points."""
        items = [
            make_work_item(id_=1, story_points=5.0, state="Closed",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=2, story_points=3.0, state="Active",
                           scope_status=ScopeStatus.CARRIED_OVER),
            make_work_item(id_=3, story_points=2.0, state="Active",
                           scope_status=ScopeStatus.COMMITTED),
        ]
        result = calculate_velocity(items)

        # carryover = 3 (carried_over, non-closed) + 2 (committed, non-closed) = 5
        assert result["team"]["carryover_points"] == 5.0
        # planned = 5 + 3 + 2 = 10
        assert result["team"]["carryover_rate"] == pytest.approx(5.0 / 10.0)

    def test_carried_over_not_delivered(self):
        """CARRIED_OVER items do NOT count toward delivered (they left the sprint)."""
        items = [
            make_work_item(id_=1, story_points=5.0, state="Closed",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=2, story_points=3.0, state="Closed",
                           scope_status=ScopeStatus.CARRIED_OVER),
        ]
        result = calculate_velocity(items)

        # delivered = only committed closed = 5 (NOT 8)
        assert result["team"]["delivered_points"] == 5.0

    def test_carried_over_tracks_scope_removed(self):
        """CARRIED_OVER points should count toward scope_removed_points."""
        items = [
            make_work_item(id_=1, story_points=5.0, state="Closed",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=2, story_points=3.0, state="Active",
                           scope_status=ScopeStatus.CARRIED_OVER),
            make_work_item(id_=3, story_points=2.0, state="Active",
                           scope_status=ScopeStatus.REMOVED),
        ]
        result = calculate_velocity(items)

        # scope_removed = 3 (carried_over) + 2 (removed) = 5
        assert result["team"]["scope_removed_points"] == 5.0
