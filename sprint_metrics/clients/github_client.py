"""GitHub API client for fetching pull requests."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from github import GithubException

from sprint_metrics.models import PullRequest


class GitHubClient:
    def __init__(self, github):
        self._gh = github

    def get_pull_requests(
        self,
        repo: str,
        start_date: datetime,
        end_date: datetime,
        team_usernames: Optional[list[str]] = None,
    ) -> list[PullRequest]:
        try:
            gh_repo = self._gh.get_repo(repo)
        except GithubException as exc:
            raise RuntimeError(
                f"Failed to access repository '{repo}': {exc.data.get('message', exc)}. "
                f"Check that the repo exists and your PAT has access."
            ) from exc
        raw_prs = gh_repo.get_pulls(state="all", sort="created", direction="desc")

        results = []
        for pr in raw_prs:
            if pr.created_at < start_date or pr.created_at > end_date:
                continue
            if team_usernames and pr.user.login not in team_usernames:
                continue

            commit_messages = [c.commit.message for c in pr.get_commits()]

            results.append(
                PullRequest(
                    id=pr.id,
                    number=pr.number,
                    title=pr.title,
                    author=pr.user.login,
                    created_at=pr.created_at,
                    merged_at=pr.merged_at,
                    closed_at=pr.closed_at,
                    repo=repo,
                    commit_messages=commit_messages,
                )
            )

        return results
