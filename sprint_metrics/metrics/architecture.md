# Metrics Architecture

## Purpose
Metrics modules calculate sprint performance indicators from domain model objects. Each module is a pure function that takes data in and returns a standardized result dict.

## Design Patterns

### Consistent return structure
Every metric function returns:
```python
{
    "team": { ... },           # Aggregated team-level stats
    "individual": {            # Per-person breakdown
        "identity_key": { ... },
    },
}
```

### Identity keys (pre-normalization)
- Work-item-based metrics (`velocity`, `cycle_time`, `rework`, `category_breakdown`) key individuals by `wi.assigned_to` (ADO email)
- PR-based metrics (`pr_cycle_time`) key individuals by `pr.author` (GitHub username)
- After calculation, `normalize_metrics_identity()` in `main.py` remaps all keys to display names

### Stateless functions
Metric modules are stateless — no classes, no side effects. They receive lists of model objects and return dicts. This makes them easy to test in isolation.

## Modules

| Module | Input | Individual Key | Key Metrics |
|---|---|---|---|
| `velocity` | `[WorkItem]` | `assigned_to` | planned_points, delivered_points, delivery_rate |
| `cycle_time` | `[WorkItem]` | `assigned_to` | average_days, median_days, count |
| `pr_cycle_time` | `[PullRequest]` | `author` | average_hours, median_hours, count |
| `rework` | `[WorkItem], labels` | `assigned_to` | rework_count, rework_points, rework_rate |
| `category_breakdown` | `[WorkItem], categories` | `assigned_to` | {category: {points, count}} |

## Special Cases

- Items with `None` story_points are excluded from point calculations but still counted
- Closed states: `{"Closed", "Done", "Resolved"}` (defined in `velocity.py`)
- Rework label matching is case-insensitive
- Category "other" is suppressed from output if its count is 0
