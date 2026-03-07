# Clients Architecture

## Purpose
Clients are responsible for fetching raw data from external systems (Azure DevOps, GitHub). They return domain model objects (`WorkItem`, `PullRequest`) and encapsulate all API-specific logic.

## Design Patterns

### Early-exit scanning
The GitHub client scans PRs in reverse chronological order and stops once it reaches PRs created before the sprint start date. This avoids paginating through the entire PR history.

### Team-scoped fetching
The GitHub client accepts an optional `team_usernames` list to filter PRs at fetch time, reducing data transfer.

### Date normalization
Config dates may be naive; clients normalize them to UTC-aware datetimes before comparing with API timestamps.

## Special Cases

- **ADO iteration paths** contain backslashes (e.g., `Project\Sprint 10`). These are constructed in `main.py`, not the client.
- **GitHub 404 errors** (private repos, wrong org) are caught and re-raised as `RuntimeError` with a helpful message about repo access.
- **PR filtering by title** (deployment PRs) happens in `main.py` after fetching, not in the client. The client stays a clean data fetcher.

## Error Handling

### Azure DevOps client
- **WIQL query failure** (`get_sprint_work_items`): Re-raised as `RuntimeError` with iteration path context. This is fatal — without work items, the pipeline cannot continue.
- **Invalid work item IDs** (`get_work_items_by_ids`): Uses a batch-then-individual fallback strategy. If a batch fetch fails (e.g., one bad ID poisons the batch), the client retries each ID individually. Invalid IDs are logged as warnings and skipped — valid items in the same batch are still returned.

### GitHub client
- **Repository access** (`get_repo`): 404/auth errors are caught and re-raised as `RuntimeError` with a helpful message.
- **Commit fetch failure** (`pr.get_commits()`): If fetching commits fails for a single PR (rate limit, deleted branch, etc.), the PR is still collected with empty `commit_messages`. A warning is logged. This means work item ID extraction from commits will be incomplete for that PR, but the PR itself is not lost.

### Logging
All clients use the `logging` module (`logging.getLogger(__name__)`). `print()` is not used. This enables structured log output and distinct warning vs. info levels.

## Identity Model
- ADO work items use `assigned_to` (email format, e.g., `jane.smith@company.com`)
- GitHub PRs use `author` (GitHub login, e.g., `janesmith`)
- Identity mapping between these two systems is handled by `TeamMember` in config, resolved in `main.py` via `normalize_metrics_identity()`
