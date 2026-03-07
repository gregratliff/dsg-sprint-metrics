"""Tests for sprint_metrics.models — Step 1 TDD."""
from datetime import datetime, timezone
import pytest

from sprint_metrics.models import WorkItem, PullRequest, SprintInfo


class TestWorkItem:
    def test_creation(self):
        wi = WorkItem(
            id=123,
            title="Implement login",
            assigned_to="jane.smith@company.com",
            story_points=5.0,
            state="Closed",
            category="strategic",
            labels=["rework", "missed-ac"],
            activated_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            closed_date=datetime(2026, 3, 4, tzinfo=timezone.utc),
            iteration_path="MyProject\\Sprint 10",
        )
        assert wi.id == 123
        assert wi.title == "Implement login"
        assert wi.assigned_to == "jane.smith@company.com"
        assert wi.story_points == 5.0
        assert wi.state == "Closed"
        assert wi.category == "strategic"
        assert wi.labels == ["rework", "missed-ac"]
        assert wi.iteration_path == "MyProject\\Sprint 10"

    def test_cycle_time_days(self):
        wi = WorkItem(
            id=1,
            title="T",
            assigned_to="a",
            story_points=3.0,
            state="Closed",
            category="strategic",
            labels=[],
            activated_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            closed_date=datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc),
            iteration_path="P\\S1",
        )
        assert wi.cycle_time_days == pytest.approx(3.5)

    def test_cycle_time_days_none_when_not_closed(self):
        wi = WorkItem(
            id=2,
            title="T",
            assigned_to="a",
            story_points=2.0,
            state="Active",
            category="defects",
            labels=[],
            activated_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            closed_date=None,
            iteration_path="P\\S1",
        )
        assert wi.cycle_time_days is None

    def test_cycle_time_days_none_when_not_activated(self):
        wi = WorkItem(
            id=3,
            title="T",
            assigned_to="a",
            story_points=1.0,
            state="New",
            category="tech_health",
            labels=[],
            activated_date=None,
            closed_date=None,
            iteration_path="P\\S1",
        )
        assert wi.cycle_time_days is None

    def test_defaults(self):
        wi = WorkItem(
            id=4,
            title="T",
            assigned_to="a",
            story_points=None,
            state="New",
            category=None,
            labels=[],
            activated_date=None,
            closed_date=None,
            iteration_path="P\\S1",
        )
        assert wi.story_points is None
        assert wi.category is None


class TestPullRequest:
    def test_creation(self):
        pr = PullRequest(
            id=1,
            number=42,
            title="Add login feature",
            author="janesmith",
            created_at=datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
            merged_at=datetime(2026, 3, 2, 14, 0, 0, tzinfo=timezone.utc),
            closed_at=datetime(2026, 3, 2, 14, 0, 0, tzinfo=timezone.utc),
            repo="myorg/repo1",
            commit_messages=["AB#123 implement login", "fix tests AB#456"],
        )
        assert pr.number == 42
        assert pr.author == "janesmith"
        assert pr.repo == "myorg/repo1"

    def test_cycle_time_hours(self):
        pr = PullRequest(
            id=1,
            number=10,
            title="T",
            author="a",
            created_at=datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
            merged_at=datetime(2026, 3, 2, 14, 0, 0, tzinfo=timezone.utc),
            closed_at=datetime(2026, 3, 2, 14, 0, 0, tzinfo=timezone.utc),
            repo="o/r",
            commit_messages=[],
        )
        assert pr.cycle_time_hours == pytest.approx(28.0)

    def test_cycle_time_hours_none_when_not_merged(self):
        pr = PullRequest(
            id=2,
            number=11,
            title="T",
            author="a",
            created_at=datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
            merged_at=None,
            closed_at=None,
            repo="o/r",
            commit_messages=[],
        )
        assert pr.cycle_time_hours is None

    def test_extract_work_item_ids_from_commit_messages(self):
        pr = PullRequest(
            id=3,
            number=12,
            title="T",
            author="a",
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            merged_at=None,
            closed_at=None,
            repo="o/r",
            commit_messages=[
                "AB#123 implement login",
                "fix tests AB#456",
                "no reference here",
                "AB#123 duplicate and AB#789",
            ],
        )
        ids = pr.extract_work_item_ids()
        assert ids == {123, 456, 789}

    def test_extract_work_item_ids_from_title_leading_number(self):
        pr = PullRequest(
            id=5,
            number=14,
            title="1422900 RouteDetails: Stop Status Code Badge",
            author="a",
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            merged_at=None,
            closed_at=None,
            repo="o/r",
        )
        assert pr.extract_work_item_ids() == {1422900}

    def test_extract_work_item_ids_from_title_ab_hash(self):
        pr = PullRequest(
            id=6,
            number=15,
            title="Fix bug AB#99999 in routing",
            author="a",
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            merged_at=None,
            closed_at=None,
            repo="o/r",
        )
        assert pr.extract_work_item_ids() == {99999}

    def test_extract_work_item_ids_from_body(self):
        pr = PullRequest(
            id=7,
            number=16,
            title="Enable drowsiness detection",
            author="a",
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            merged_at=None,
            closed_at=None,
            repo="o/r",
            body="Related to AB#54321 and AB#67890",
        )
        assert pr.extract_work_item_ids() == {54321, 67890}

    def test_extract_work_item_ids_combined_sources(self):
        pr = PullRequest(
            id=8,
            number=17,
            title="1430241 driver scorecard fix",
            author="a",
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            merged_at=None,
            closed_at=None,
            repo="o/r",
            body="Also fixes AB#99999",
            commit_messages=["AB#11111 commit msg"],
        )
        assert pr.extract_work_item_ids() == {1430241, 99999, 11111}

    def test_extract_work_item_ids_empty(self):
        pr = PullRequest(
            id=4,
            number=13,
            title="T",
            author="a",
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            merged_at=None,
            closed_at=None,
            repo="o/r",
            commit_messages=["no references"],
        )
        assert pr.extract_work_item_ids() == set()

    def test_extract_work_item_ids_short_number_not_matched(self):
        """Leading numbers shorter than 5 digits should not match as work item IDs."""
        pr = PullRequest(
            id=9,
            number=18,
            title="1234 short number title",
            author="a",
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            merged_at=None,
            closed_at=None,
            repo="o/r",
        )
        assert pr.extract_work_item_ids() == set()


class TestSprintInfo:
    def test_creation(self):
        si = SprintInfo(
            name="Sprint 23.1",
            start_date=datetime(2026, 2, 23, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 6, tzinfo=timezone.utc),
            team="Team Alpha",
        )
        assert si.name == "Sprint 23.1"
        assert si.team == "Team Alpha"

    def test_duration_days(self):
        si = SprintInfo(
            name="S1",
            start_date=datetime(2026, 2, 23, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 6, tzinfo=timezone.utc),
            team="T",
        )
        assert si.duration_days == 11
