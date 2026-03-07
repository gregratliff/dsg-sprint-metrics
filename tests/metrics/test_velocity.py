"""Tests for sprint_metrics.metrics.velocity — Step 5 TDD."""

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

    def test_carried_over_closed_still_counts_as_carryover(self):
        """CARRIED_OVER items always count as carryover, even if closed in the next sprint.

        planned must equal delivered + carryover + removed (non-carryover).
        A carried-over item closed in the next sprint wasn't delivered HERE.
        """
        items = [
            make_work_item(id_=1, story_points=5.0, state="Closed",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=2, story_points=3.0, state="Closed",
                           scope_status=ScopeStatus.CARRIED_OVER),
        ]
        result = calculate_velocity(items)

        # delivered = 5 (only committed), carryover = 3 (carried_over, even though closed)
        assert result["team"]["delivered_points"] == 5.0
        assert result["team"]["carryover_points"] == 3.0
        assert result["team"]["planned_points"] == 8.0
        # Invariant: planned == delivered + carryover + scope_removed(non-carryover)
        # Here: 8 = 5 + 3 + 0 ✓

    def test_scope_removed_excludes_carried_over(self):
        """scope_removed_points only counts REMOVED, not CARRIED_OVER."""
        items = [
            make_work_item(id_=1, story_points=5.0, state="Closed",
                           scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=2, story_points=3.0, state="Active",
                           scope_status=ScopeStatus.CARRIED_OVER),
            make_work_item(id_=3, story_points=2.0, state="Active",
                           scope_status=ScopeStatus.REMOVED),
        ]
        result = calculate_velocity(items)

        # scope_removed = only REMOVED = 2 (CARRIED_OVER is in carryover_points)
        assert result["team"]["scope_removed_points"] == 2.0
        assert result["team"]["carryover_points"] == 3.0  # only carried_over (REMOVED not in carryover)

    def test_individual_scope_stats(self):
        """Individual members should have all scope-related stats."""
        items = [
            # Jane: 5 committed closed, 3 committed active, 2 added closed
            make_work_item(id_=1, assigned_to="jane", story_points=5.0,
                           state="Closed", scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=2, assigned_to="jane", story_points=3.0,
                           state="Active", scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=3, assigned_to="jane", story_points=2.0,
                           state="Closed", scope_status=ScopeStatus.ADDED_MID_SPRINT),
            # John: 8 committed closed, 4 carried over, 2 removed
            make_work_item(id_=4, assigned_to="john", story_points=8.0,
                           state="Closed", scope_status=ScopeStatus.COMMITTED),
            make_work_item(id_=5, assigned_to="john", story_points=4.0,
                           state="Active", scope_status=ScopeStatus.CARRIED_OVER),
            make_work_item(id_=6, assigned_to="john", story_points=2.0,
                           state="Active", scope_status=ScopeStatus.REMOVED),
        ]
        result = calculate_velocity(items)

        jane = result["individual"]["jane"]
        # jane planned = 5 + 3 = 8 (committed only, added doesn't count)
        assert jane["planned_points"] == 8.0
        assert jane["delivered_points"] == 7.0  # 5 committed + 2 added
        assert jane["delivery_rate"] == pytest.approx(7.0 / 8.0)
        assert jane["scope_added_points"] == 2.0
        assert jane["scope_removed_points"] == 0.0
        assert jane["carryover_points"] == 3.0  # active committed
        assert jane["carryover_rate"] == pytest.approx(3.0 / 8.0)
        # commitment_reliability = closed committed / planned = 5/8
        assert jane["commitment_reliability"] == pytest.approx(5.0 / 8.0)

        john = result["individual"]["john"]
        # john planned = 8 + 4 + 2 = 14 (committed + carried_over + removed)
        assert john["planned_points"] == 14.0
        assert john["delivered_points"] == 8.0  # only committed closed
        assert john["delivery_rate"] == pytest.approx(8.0 / 14.0)
        assert john["scope_added_points"] == 0.0
        assert john["scope_removed_points"] == 2.0  # only REMOVED (not carried_over)
        assert john["carryover_points"] == 4.0  # carried_over always counts
        assert john["carryover_rate"] == pytest.approx(4.0 / 14.0)
        assert john["commitment_reliability"] == pytest.approx(8.0 / 14.0)

    def test_planned_invariant(self):
        """planned == delivered + carryover + removed for all scope statuses.

        Note: delivered_points includes ADDED_MID_SPRINT items which are NOT
        planned, so the invariant accounts for scope_added.
        """
        items = [
            # Committed closed → delivered
            make_work_item(id_=1, story_points=5.0, state="Closed",
                           scope_status=ScopeStatus.COMMITTED),
            # Committed active → carryover
            make_work_item(id_=2, story_points=3.0, state="Active",
                           scope_status=ScopeStatus.COMMITTED),
            # Added closed → delivered (not planned, so outside invariant)
            make_work_item(id_=3, story_points=2.0, state="Closed",
                           scope_status=ScopeStatus.ADDED_MID_SPRINT),
            # Carried over → carryover
            make_work_item(id_=4, story_points=4.0, state="Active",
                           scope_status=ScopeStatus.CARRIED_OVER),
            # Carried over but closed in next sprint → still carryover
            make_work_item(id_=5, story_points=6.0, state="Closed",
                           scope_status=ScopeStatus.CARRIED_OVER),
            # Removed → removed
            make_work_item(id_=6, story_points=1.0, state="Active",
                           scope_status=ScopeStatus.REMOVED),
        ]
        result = calculate_velocity(items)
        t = result["team"]

        # planned = 5 + 3 + 4 + 6 + 1 = 19 (committed + carried_over + removed)
        assert t["planned_points"] == 19.0
        # delivered = 5 + 2 = 7 (closed committed + closed added)
        assert t["delivered_points"] == 7.0
        # carryover = 3 + 4 + 6 = 13 (non-closed committed + all carried_over)
        assert t["carryover_points"] == 13.0
        # removed = 1 (only REMOVED)
        assert t["scope_removed_points"] == 1.0
        # added = 2 (scope creep)
        assert t["scope_added_points"] == 2.0

        # THE INVARIANT: planned = (delivered - added) + carryover + removed
        # delivered includes ADDED items which aren't planned, so subtract them
        assert t["planned_points"] == pytest.approx(
            (t["delivered_points"] - t["scope_added_points"])
            + t["carryover_points"]
            + t["scope_removed_points"]
        )
