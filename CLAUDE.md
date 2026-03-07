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

### 4. Type safety and linting

- Run `python -m mypy sprint_metrics/ --strict` — fix all type errors.
- Run `python -m ruff check sprint_metrics/ tests/` — fix all lint violations.
- These are enforced by Stop hooks and will block if they fail.

### 5. Verify test coverage

- Coverage must remain at or above **80%** (enforced by pytest-cov in `pyproject.toml`).
- If coverage drops, add tests before proceeding.

### 6. Update documentation

- Update `architecture.md` files in any domain folders affected by the change.
- Document new patterns, error handling strategies, gotchas, and important context for future modifications.

### 7. Code review (automatic)

- The `code-reviewer` subagent runs automatically on Stop when files are changed.
- It checks 4 dimensions: architecture, security, performance, and dependency CVEs.
- Address any WARN or FAIL findings before considering the change complete.

## Quality Gates (enforced by hooks)

The following checks run automatically on every Stop via `.claude/settings.json`:

1. **Tests + Coverage**: `pytest` with `--cov-fail-under=80` — all tests must pass
2. **Type checking**: `mypy --strict` — no type errors allowed
3. **Linting**: `ruff check` — no lint violations allowed

If any gate fails, fix the issue before finishing.

## Type Checking Standards

- `mypy --strict` must pass on all production code.
- All function parameters and return types must be annotated.
- Use `T | None` syntax (not `Optional[T]`).
- Use `Any` for untyped third-party SDK types (azure-devops, PyGithub) with `ignore_missing_imports` in `pyproject.toml`.
- No `type: ignore` without a comment explaining why.

## Testing Standards

- Tests live in `tests/` mirroring the source structure.
- Use `pytest` and `unittest.mock` for mocking external dependencies.
- External API calls (ADO, GitHub) are always mocked in tests.
- Test files are named `test_<module>.py`.
- Minimum coverage threshold: **80%** (currently at 95%).

## Error Handling Philosophy

- **Warn and continue** for non-fatal issues (bad work item IDs, single PR commit fetch failures, single repo failures). Use `logger.warning()`.
- **Fail fast with context** for truly fatal issues (WIQL query failure, missing PATs). Re-raise as `RuntimeError` with a helpful message.
- **Never crash silently** — every caught exception must produce a log message.

## Logging and Instrumentation

- Use `logging.getLogger(__name__)` in every module — never `print()`.
- `logger.info()` for progress messages and pipeline entry points.
- `logger.warning()` for recoverable issues that may affect report completeness.
- `logger.error()` for fatal issues.
- `logger.debug()` for detailed troubleshooting data.
- Use %-style formatting: `logger.info("Found %d items", count)` — not f-strings.
- See `.claude/skills/instrumentation/SKILL.md` for detailed patterns.

## Python Security Rules

- Always use `yaml.safe_load()` — never `yaml.load()`.
- Never use `pickle.loads()`, `eval()`, `exec()`, or `compile()` on external data.
- Never use `subprocess.run(..., shell=True)` — pass args as a list.
- Access PATs only via environment variables — never hardcode.
- No sensitive data in log messages or error output.

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
.claude/
  agents/          # Subagents (code-reviewer)
  skills/          # Skills (instrumentation)
  settings.json    # Stop hooks for quality gates
```

Each domain folder contains an `architecture.md` documenting patterns and decisions.
