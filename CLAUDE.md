# CLAUDE.md — Project Rules for Sprint Metrics Tool

## Development Workflow: TDD (RED-GREEN-REFACTOR)

All code changes MUST follow this workflow. Do not skip steps.

### 1. RED — Write failing tests FIRST

- Identify what tests need to be added or modified for the change.
- Write those tests before touching any production code.
- Run the test suite to confirm the new/modified tests are **failing**.
- If a new test passes immediately, it is not testing anything useful — iterate on it until it fails.

### 2. GREEN — Write the minimum production code to pass

- Implement only what is needed to make the failing tests pass.
- Run the **entire** test suite (`python -m pytest tests/`), not just the new tests.
- ALL tests must be green before proceeding. If any test fails, fix it before moving on.

### 3. REFACTOR — Clean up without changing behavior

- Remove duplication, improve naming, extract shared logic.
- Run the **entire** test suite again to confirm nothing broke.
- ALL tests must remain green.

### 4. Update documentation

- Update `architecture.md` files in any domain folders affected by the change.
- Document new patterns, error handling strategies, gotchas, and important context for future modifications.

## Testing Standards

- Tests live in `tests/` mirroring the source structure.
- Use `pytest` and `unittest.mock` for mocking external dependencies.
- External API calls (ADO, GitHub) are always mocked in tests.
- Test files are named `test_<module>.py`.

## Error Handling Philosophy

- **Warn and continue** for non-fatal issues (bad work item IDs, single PR commit fetch failures, single repo failures). Use `logger.warning()`.
- **Fail fast with context** for truly fatal issues (WIQL query failure, missing PATs). Re-raise as `RuntimeError` with a helpful message.
- **Never crash silently** — every caught exception must produce a log message.

## Logging

- Use `logging.getLogger(__name__)` in every module — never `print()`.
- `logger.info()` for progress messages.
- `logger.warning()` for recoverable issues that may affect report completeness.
- `logger.error()` for fatal issues.

## Project Structure

```
sprint_metrics/
  clients/         # External API clients (ADO, GitHub)
  metrics/         # Pure stateless metric calculators
  reports/         # Report output formatters (CSV)
  models.py        # Domain model dataclasses
  config.py        # Config loading and validation
  main.py          # CLI entrypoint and pipeline orchestration
tests/             # Mirrors source structure
```

Each domain folder contains an `architecture.md` documenting patterns and decisions.
