---
description: Instrumentation and observability patterns for the Sprint Metrics Tool. Apply these patterns when adding or modifying Python code to ensure proper logging and observability.
user-invocable: false
---

When adding or modifying code in this project, ensure proper instrumentation following these patterns:

## Logging Standards

- Use `logging.getLogger(__name__)` in every module — never `print()`
- `logger.info()` at pipeline entry points and API call boundaries
- `logger.warning()` for recoverable issues that may affect report completeness
- `logger.error()` for fatal issues, always with exception context
- `logger.debug()` for detailed data useful during troubleshooting
- Use %-style formatting for log messages: `logger.info("Fetching PRs for %s", repo)` — not f-strings

## When to Add Logging

- **New API calls**: Log before the call (what's being fetched) and after (count of results)
- **Data filtering**: Log how many items were filtered and why
- **Error recovery**: Log the exception, what was attempted, and how we're recovering
- **Pipeline stages**: Log entry with key parameters and exit with result counts
- **Fallback behavior**: Log when a fallback is triggered (e.g., batch → individual retry)

## Error Context

Every caught exception must include:
- What operation was attempted
- What input caused the failure
- Whether processing continues (warning) or stops (error/RuntimeError)

Example:
```python
try:
    items = client.get_work_items(ids)
except Exception:
    logger.warning("Failed to fetch work items %s — skipping", ids)
    items = []
```

## Anti-patterns to Avoid

- `print()` statements anywhere in production code
- Silent exception swallowing (`except: pass`)
- Logging sensitive data (PATs, tokens, full API responses)
- f-strings in logger calls (`logger.info(f"Found {count}")` — use `logger.info("Found %d", count)`)
