"""Tests for sprint_metrics.clients.github_client — Step 4 TDD."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, PropertyMock

import pytest
from github import GithubException

from sprint_metrics.clients.github_client import GitHubClient
from sprint_metrics.models import PullRequest


def _make_mock_pr(
    number=1,
    title="Add feature",
    user_login="janesmith",
    created_at=datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
    merged_at=datetime(2026, 3, 2, 14, 0, 0, tzinfo=timezone.utc),
    closed_at=datetime(2026, 3, 2, 14, 0, 0, tzinfo=timezone.utc),
    updated_at=None,
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
    pr.updated_at = updated_at or merged_at or closed_at or created_at

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

    def test_filters_by_merge_date(self):
        """Only PRs merged within the sprint window are included."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        # Merged during sprint — included
        merged_in_sprint = _make_mock_pr(
            number=1,
            created_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
            merged_at=datetime(2026, 3, 3, tzinfo=timezone.utc),
        )
        # Merged before sprint — excluded
        merged_before = _make_mock_pr(
            number=2,
            created_at=datetime(2026, 2, 15, tzinfo=timezone.utc),
            merged_at=datetime(2026, 2, 16, tzinfo=timezone.utc),
            updated_at=datetime(2026, 3, 5, tzinfo=timezone.utc),  # updated during sprint (e.g. comment)
        )
        # Created during sprint but not merged — excluded
        unmerged = _make_mock_pr(
            number=3,
            created_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
            merged_at=None,
            closed_at=None,
            updated_at=datetime(2026, 3, 4, tzinfo=timezone.utc),
        )
        # Merged after sprint — excluded
        merged_after = _make_mock_pr(
            number=4,
            created_at=datetime(2026, 3, 5, tzinfo=timezone.utc),
            merged_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            updated_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
        )
        mock_repo.get_pulls.return_value = [
            merged_after, unmerged, merged_in_sprint, merged_before,
        ]

        client = self._make_client(mock_gh)
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )

        assert len(prs) == 1
        assert prs[0].number == 1

    def test_pr_created_before_sprint_merged_during_sprint(self):
        """A PR created months ago but merged during the sprint is included."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        old_pr_merged_now = _make_mock_pr(
            number=42,
            created_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            merged_at=datetime(2026, 3, 4, tzinfo=timezone.utc),
        )
        mock_repo.get_pulls.return_value = [old_pr_merged_now]

        client = self._make_client(mock_gh)
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )

        assert len(prs) == 1
        assert prs[0].number == 42

    def test_unmerged_pr_excluded(self):
        """Unmerged PRs are excluded — only merged PRs belong to a sprint."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pulls.return_value = [
            _make_mock_pr(merged_at=None, closed_at=None,
                          updated_at=datetime(2026, 3, 3, tzinfo=timezone.utc))
        ]

        client = self._make_client(mock_gh)
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )

        assert len(prs) == 0

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

    def test_early_exit_skips_old_prs(self):
        """Scanning stops at first PR whose updated_at is before start_date."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        # Sorted by updated desc: in-range, then old, then even-older
        in_range = _make_mock_pr(
            number=10,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            merged_at=datetime(2026, 3, 3, tzinfo=timezone.utc),
            updated_at=datetime(2026, 3, 3, tzinfo=timezone.utc),
        )
        old_pr = _make_mock_pr(
            number=5,
            created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            merged_at=datetime(2026, 2, 2, tzinfo=timezone.utc),
            updated_at=datetime(2026, 2, 2, tzinfo=timezone.utc),
        )
        even_older = _make_mock_pr(
            number=1,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            merged_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        mock_repo.get_pulls.return_value = [in_range, old_pr, even_older]

        client = self._make_client(mock_gh)
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )

        assert len(prs) == 1
        assert prs[0].number == 10
        # even_older should never have get_commits called (we broke early at old_pr)
        even_older.get_commits.assert_not_called()

    def test_naive_dates_work_with_aware_github_dates(self):
        """Naive config dates are normalized to UTC for comparison."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_repo.get_pulls.return_value = [
            _make_mock_pr(
                number=1,
                created_at=datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc),
            )
        ]

        client = self._make_client(mock_gh)
        # Pass naive datetimes (no tzinfo), like datetime.fromisoformat("2026-03-01")
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1),
            end_date=datetime(2026, 3, 7),
        )

        assert len(prs) == 1
        assert prs[0].number == 1

    def test_get_commits_failure_continues_with_empty_messages(self):
        """If get_commits() fails for a PR, the PR is still returned with empty commit_messages."""
        mock_gh = MagicMock()
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        pr_with_failing_commits = _make_mock_pr(number=1, title="AB#100 feature")
        pr_with_failing_commits.get_commits.side_effect = Exception("API rate limit")
        pr_with_failing_commits.body = ""

        mock_repo.get_pulls.return_value = [pr_with_failing_commits]

        client = self._make_client(mock_gh)
        prs = client.get_pull_requests(
            repo="myorg/repo1",
            start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
        )

        assert len(prs) == 1
        assert prs[0].commit_messages == []

    def test_repo_not_found_raises_runtime_error(self):
        """404 from GitHub is wrapped in a RuntimeError with helpful message."""
        mock_gh = MagicMock()
        exc = GithubException(404, {"message": "Not Found"}, None)
        mock_gh.get_repo.side_effect = exc

        client = self._make_client(mock_gh)
        with pytest.raises(RuntimeError, match="Failed to access repository 'myorg/missing'"):
            client.get_pull_requests(
                repo="myorg/missing",
                start_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
                end_date=datetime(2026, 3, 7, tzinfo=timezone.utc),
            )
