# Clients Architecture

## Purpose
Clients are responsible for fetching raw data from external systems (Azure DevOps, GitHub). They return domain model objects (`WorkItem`, `PullRequest`) and encapsulate all API-specific logic.

## Design Patterns

### Merge-date filtering
PRs belong to a sprint if they were **merged** within the sprint window (`start_date <= merged_at <= end_date`). Unmerged PRs and PRs merged outside the window are excluded, regardless of when they were created. This ensures accurate "work completed" metrics.

### Early-exit scanning
The GitHub client fetches closed PRs sorted by `updated_at` descending and stops once `updated_at` falls before the sprint start date. Since `updated_at >= merged_at`, any PR merged during the sprint will have `updated_at >= start_date`, so the early exit is safe.

### Team-scoped fetching
The GitHub client accepts an optional `team_usernames` list to filter PRs at fetch time, reducing data transfer.

### ASOF queries for sprint scope tracking
The ADO client supports `get_sprint_work_items_asof(iteration_path, asof_date)` which appends `ASOF '{date}'` to the WIQL query. This returns work items as they existed at a specific point in time. The pipeline uses two ASOF queries:
- **Planning snapshot** (`start_date + planning_offset_days`): what was committed after planning settled
- **End-of-sprint snapshot** (`end_date`): what was in the sprint when it ended (or current state if sprint is in progress)

### Carryover detection
For items that left the sprint (in planning snapshot but not end-of-sprint), the pipeline uses `get_work_items_by_ids` to fetch their **current** state. This reveals whether the item was moved to another sprint iteration (CARRIED_OVER) or to the backlog/deleted (REMOVED). The current iteration path is compared against the sprint's iteration path to make this distinction.

### Date normalization
Config dates may be naive; clients normalize them to UTC-aware datetimes before comparing with API timestamps.

## Special Cases

- **ADO iteration paths** contain backslashes (e.g., `Project\Sprint 10`). These are constructed in `main.py`, not the client.
- **GitHub 404 errors** (private repos, wrong org) are caught and re-raised as `RuntimeError` with a helpful message about repo access.
- **PR filtering by title** (deployment PRs) happens in `main.py` after fetching, not in the client. The client stays a clean data fetcher. Revert chains (`Revert "Revert "..."..."`) are automatically unwrapped before matching, so patterns don't need to account for reverts.

## Error Handling

### Azure DevOps client
- **WIQL query failure** (`get_sprint_work_items`): Re-raised as `RuntimeError` with iteration path context. This is fatal — without work items, the pipeline cannot continue.
- **Invalid work item IDs** (`get_work_items_by_ids`): Uses a batch-then-individual fallback strategy. If a batch fetch fails (e.g., one bad ID poisons the batch), the client retries each ID individually. Invalid IDs are logged as warnings and skipped — valid items in the same batch are still returned.

### GitHub client
- **Repository access** (`get_repo`): 404/auth errors are caught and re-raised as `RuntimeError` with a helpful message.
- **Commit fetch failure** (`pr.get_commits()`): If fetching commits fails for a single PR (rate limit, deleted branch, etc.), the PR is still collected with empty `commit_messages`. A warning is logged. This means work item ID extraction from commits will be incomplete for that PR, but the PR itself is not lost.

### Logging
All clients use the `logging` module (`logging.getLogger(__name__)`). `print()` is not used. This enables structured log output and distinct warning vs. info levels.

## Type Safety

- Client constructors accept `Any` for external SDK types (azure-devops `Connection`, PyGithub `Github`) since these libraries lack type stubs.
- All internal types are fully annotated — `mypy --strict` passes.
- The `_parse_date()` helper accepts `str | datetime | None` to handle both raw API strings and pre-parsed datetime objects.
- WIQL query strings are flagged by ruff's S608 rule but suppressed via per-file ignore in `pyproject.toml` — WIQL uses controlled internal input, not user-supplied strings.

## Identity Model
- ADO work items use `assigned_to` (email format, e.g., `jane.smith@company.com`)
- GitHub PRs use `author` (GitHub login, e.g., `janesmith`)
- Identity mapping between these two systems is handled by `TeamMember` in config, resolved in `main.py` via `normalize_metrics_identity()`
