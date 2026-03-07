"""Shared test fixtures."""
from datetime import datetime, timezone

import pytest

from sprint_metrics.models import WorkItem, PullRequest, SprintInfo, ScopeStatus


@pytest.fixture
def sprint_info():
    return SprintInfo(
        name="Sprint 10",
        start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 14, tzinfo=timezone.utc),
        team="Team Alpha",
    )


def make_work_item(
    id_=1,
    title="Task",
    assigned_to="jane.smith@company.com",
    story_points=3.0,
    state="Closed",
    category="strategic",
    labels=None,
    activated_date=datetime(2026, 3, 2, tzinfo=timezone.utc),
    closed_date=datetime(2026, 3, 5, tzinfo=timezone.utc),
    iteration_path="P\\Sprint 10",
    scope_status=ScopeStatus.COMMITTED,
):
    return WorkItem(
        id=id_,
        title=title,
        assigned_to=assigned_to,
        story_points=story_points,
        state=state,
        category=category,
        labels=labels or [],
        activated_date=activated_date,
        closed_date=closed_date,
        iteration_path=iteration_path,
        scope_status=scope_status,
    )


def make_pull_request(
    number=1,
    author="janesmith",
    created_at=datetime(2026, 3, 2, 10, 0, 0, tzinfo=timezone.utc),
    merged_at=datetime(2026, 3, 3, 14, 0, 0, tzinfo=timezone.utc),
    commit_messages=None,
):
    return PullRequest(
        id=number * 100,
        number=number,
        title=f"PR #{number}",
        author=author,
        created_at=created_at,
        merged_at=merged_at,
        closed_at=merged_at,
        repo="myorg/repo1",
        commit_messages=commit_messages or [],
    )
