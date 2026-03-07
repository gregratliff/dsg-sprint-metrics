"""GitHub API client for fetching pull requests."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from github import GithubException

from sprint_metrics.models import PullRequest

logger = logging.getLogger(__name__)


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
        # Ensure dates are timezone-aware for comparison with GitHub's UTC datetimes
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        raw_prs = gh_repo.get_pulls(state="all", sort="created", direction="desc")

        results = []
        scanned = 0
        for pr in raw_prs:
            scanned += 1
            # PRs are sorted newest-first; stop once we're before the sprint window
            if pr.created_at < start_date:
                logger.info("  Scanned %d PRs, reached pre-sprint date, stopping", scanned)
                break
            if pr.created_at > end_date:
                continue
            if team_usernames and pr.user.login not in team_usernames:
                continue

            logger.info("  PR #%d: %s (%s)", pr.number, pr.title, pr.user.login)
            try:
                commit_messages = [c.commit.message for c in pr.get_commits()]
            except Exception:
                logger.warning(
                    "  Failed to fetch commits for PR #%d — continuing without commit messages",
                    pr.number,
                )
                commit_messages = []

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
                    body=pr.body or "",
                    commit_messages=commit_messages,
                )
            )

        logger.info("  Found %d matching PRs in %s", len(results), repo)
        return results
