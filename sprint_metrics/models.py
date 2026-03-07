"""Data models for sprint metrics."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ScopeStatus(StrEnum):
    COMMITTED = "committed"
    ADDED_MID_SPRINT = "added"
    REMOVED = "removed"
    CARRIED_OVER = "carried_over"


@dataclass
class WorkItem:
    id: int
    title: str
    assigned_to: str
    story_points: float | None
    state: str
    category: str | None
    labels: list[str]
    activated_date: datetime | None
    closed_date: datetime | None
    iteration_path: str
    scope_status: ScopeStatus = ScopeStatus.COMMITTED

    @property
    def cycle_time_days(self) -> float | None:
        if self.activated_date is None or self.closed_date is None:
            return None
        delta = self.closed_date - self.activated_date
        return delta.total_seconds() / 86400


@dataclass
class PullRequest:
    id: int
    number: int
    title: str
    author: str
    created_at: datetime
    merged_at: datetime | None
    closed_at: datetime | None
    repo: str
    body: str = ""
    commit_messages: list[str] = field(default_factory=list)

    @property
    def cycle_time_hours(self) -> float | None:
        if self.merged_at is None:
            return None
        delta = self.merged_at - self.created_at
        return delta.total_seconds() / 3600

    def extract_work_item_ids(self) -> set[int]:
        """Extract ADO work item IDs from PR title and commit messages.

        Matches AB#12345 patterns in commit messages and leading numeric IDs
        in the PR title (e.g., '1422900 RouteDetails: Stop Status Code Badge').
        """
        ids: set[int] = set()
        # Check for leading numeric ID in title
        title_match = re.match(r"^(\d{5,})\b", self.title)
        if title_match:
            ids.add(int(title_match.group(1)))
        # Check for AB#ID patterns in title, body, and commit messages
        for text in [self.title, self.body, *self.commit_messages]:
            for match in re.finditer(r"AB#(\d+)", text):
                ids.add(int(match.group(1)))
        return ids


@dataclass
class SprintInfo:
    name: str
    start_date: datetime
    end_date: datetime
    team: str

    @property
    def duration_days(self) -> int:
        return (self.end_date - self.start_date).days
