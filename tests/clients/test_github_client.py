"""Tests for sprint_metrics.clients.github_client — Step 4 TDD."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, PropertyMock

import pytest

from sprint_metrics.clients.github_client import GitHubClient
from sprint_metrics.models import PullRequest


def _make_mock_pr(
    number=1,
    title="Add feature",
    user_login="janesmith",
    created_at=datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
    merged_at=datetime(2026, 3, 2, 14, 0, 0, tzinfo=timezone.utc),
    closed_at=datetime(2026, 3, 2, 14, 0, 0, tzinfo=timezone.utc),
    commit_messages=None,
):
    pr = MagicMock()
    pr.id = number * 100
    pr.number = number
    pr.title = title
    pr.user.login = user_login
    pr.created_at = created_at
    pr.merged_at = merged_at
    pr.closed_at = closed_at

    if commit_messages is None:
        commit_messages = ["AB#123 implement feature"]

    commits = []
    for msg in commit_messages:
        c = MagicMock()
        c.commit.message = msg
        commits.append(c)

    pr.get_commits.return_value = commits
    return pr


class TestGitHubClient:
    def _make_client(self, mock_github=None):
        gh = mock_github or MagicMock()
        return GitHubClient(github=gh)

    def test_get_pull_requests_returns_models(self):
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pulls.return_value = [_make_mock_pr()]

        client = self._make_client(mock_gh)
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )

        assert len(prs) == 1
        assert isinstance(prs[0], PullRequest)
        assert prs[0].number == 1
        assert prs[0].author == "janesmith"
        assert prs[0].repo == "myorg/repo1"

    def test_commit_messages_collected(self):
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pulls.return_value = [
            _make_mock_pr(commit_messages=["AB#100 first", "AB#200 second"])
        ]

        client = self._make_client(mock_gh)
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )

        assert prs[0].commit_messages == ["AB#100 first", "AB#200 second"]

    def test_filters_by_date_range(self):
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        in_range = _make_mock_pr(
            number=1,
            created_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
        )
        before_range = _make_mock_pr(
            number=2,
            created_at=datetime(2026, 2, 15, tzinfo=timezone.utc),
            merged_at=datetime(2026, 2, 16, tzinfo=timezone.utc),
            closed_at=datetime(2026, 2, 16, tzinfo=timezone.utc),
        )
        after_range = _make_mock_pr(
            number=3,
            created_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            merged_at=None,
            closed_at=None,
        )
        mock_repo.get_pulls.return_value = [in_range, before_range, after_range]

        client = self._make_client(mock_gh)
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )

        assert len(prs) == 1
        assert prs[0].number == 1

    def test_unmerged_pr(self):
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pulls.return_value = [
            _make_mock_pr(merged_at=None, closed_at=None)
        ]

        client = self._make_client(mock_gh)
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )

        assert len(prs) == 1
        assert prs[0].merged_at is None
        assert prs[0].cycle_time_hours is None

    def test_empty_repo(self):
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pulls.return_value = []

        client = self._make_client(mock_gh)
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )

        assert prs == []

    def test_filters_by_team_members(self):
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        team_pr = _make_mock_pr(number=1, user_login="janesmith")
        outside_pr = _make_mock_pr(number=2, user_login="outsider")
        mock_repo.get_pulls.return_value = [team_pr, outside_pr]

        client = self._make_client(mock_gh)
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
            team_usernames=["janesmith", "johndoe"],
        )

        assert len(prs) == 1
        assert prs[0].author == "janesmith"

    def test_no_team_filter_returns_all(self):
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pulls.return_value = [
            _make_mock_pr(number=1, user_login="a"),
            _make_mock_pr(number=2, user_login="b"),
        ]

        client = self._make_client(mock_gh)
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )

        assert len(prs) == 2
