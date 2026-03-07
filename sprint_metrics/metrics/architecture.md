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
| `velocity` | `[WorkItem]` | `assigned_to` | planned_points, delivered_points, delivery_rate, scope_added/removed, carryover, commitment_reliability |
| `cycle_time` | `[WorkItem]` | `assigned_to` | average_days, median_days, count (COMMITTED + ADDED only) |
| `pr_cycle_time` | `[PullRequest]` | `author` | average_hours, median_hours, count |
| `rework` | `[WorkItem], labels` | `assigned_to` | rework_count, rework_points, rework_rate |
| `category_breakdown` | `[WorkItem], categories` | `assigned_to` | {category: {points, count}} |

## Special Cases

- Items with `None` story_points are excluded from point calculations but still counted
- Closed states: `{"Closed", "Done", "Resolved"}` (defined in `velocity.py`)
- Rework label matching is case-insensitive
- Category "other" is suppressed from output if its count is 0
- Cycle time excludes REMOVED and CARRIED_OVER items — they left the sprint, so their completion time belongs to wherever they landed
- CARRIED_OVER items always count as carryover even if closed (in the next sprint), since they weren't delivered in the measured sprint. This ensures the invariant: planned = delivered + carryover + removed(non-carryover)

## Scope-Aware Velocity

Work items carry a `scope_status` set by `classify_sprint_scope()` in `main.py`. There are four statuses:

- **COMMITTED**: in both planning and end-of-sprint snapshots
- **ADDED_MID_SPRINT**: only in end-of-sprint snapshot (scope creep)
- **REMOVED**: only in planning snapshot and NOT moved to another sprint (descoped to backlog)
- **CARRIED_OVER**: only in planning snapshot but moved to a different sprint iteration

The velocity calculator uses scope_status as follows:

- **planned_points** = COMMITTED + REMOVED + CARRIED_OVER (what was in the planning snapshot)
- **delivered_points** = closed items that are COMMITTED or ADDED_MID_SPRINT
- **scope_added_points** = ADDED_MID_SPRINT points
- **scope_removed_points** = REMOVED + CARRIED_OVER points (all items that left the sprint)
- **carryover_points** = non-closed COMMITTED/ADDED items + **all** CARRIED_OVER items (regardless of closed state — they weren't delivered in *this* sprint)
- **commitment_reliability** = closed COMMITTED items / planned_points

### Carryover detection

To distinguish REMOVED from CARRIED_OVER, the pipeline fetches the **current state** of items that left the sprint (via `get_work_items_by_ids`). If the item's current `iteration_path` is a different sprint (not a parent/backlog path), it's CARRIED_OVER. If it's on the backlog, deleted, or not found, it stays REMOVED.

The heuristic: if `sprint_iteration_path` starts with `current_iteration_path`, the item was moved to a parent (backlog) → REMOVED. Otherwise, if the paths differ → CARRIED_OVER.
