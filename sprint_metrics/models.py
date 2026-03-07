"""Data models for sprint metrics."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class WorkItem:
    id: int
    title: str
    assigned_to: str
    story_points: Optional[float]
    state: str
    category: Optional[str]
    labels: list[str]
    activated_date: Optional[datetime]
    closed_date: Optional[datetime]
    iteration_path: str

    @property
    def cycle_time_days(self) -> Optional[float]:
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
    merged_at: Optional[datetime]
    closed_at: Optional[datetime]
    repo: str
    commit_messages: list[str] = field(default_factory=list)

    @property
    def cycle_time_hours(self) -> Optional[float]:
        if self.merged_at is None:
            return None
        delta = self.merged_at - self.created_at
        return delta.total_seconds() / 3600

    def extract_work_item_ids(self) -> set[int]:
        ids: set[int] = set()
        for msg in self.commit_messages:
            for match in re.finditer(r"AB#(\d+)", msg):
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
