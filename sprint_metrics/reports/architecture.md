# Reports Architecture

## Purpose
Report modules format calculated metrics into output files. Currently supports CSV output.

## Design Patterns

### Single entry point
`write_sprint_report(metrics, output_path)` takes the full metrics dict and writes a complete CSV.

### Dynamic columns
Category columns are determined at runtime from the actual data. The "other" category is only included if it has items.

### Row structure
- First row: `TEAM` — aggregated team-level stats (ado_identity and github_username are empty)
- Subsequent rows: one per team member (sorted alphabetically by display name)

### Identity columns
Each member row includes:
- `member` — display name from config (e.g., "Jane Smith")
- `ado_identity` — ADO email (e.g., "jane.smith@company.com")
- `github_username` — GitHub login (e.g., "janesmith")

This allows downstream consumers to join on any identity system.

## Column Order
```
sprint, member, ado_identity, github_username,
planned_points, delivered_points, delivery_rate,
avg_cycle_time_days, median_cycle_time_days, cycle_time_count,
avg_pr_cycle_time_hours, median_pr_cycle_time_hours, pr_count,
rework_count, rework_points, rework_rate,
[category_points, category_count, ...]
```

## Special Cases

- Missing metric data uses empty string (`""`) rather than 0, so consumers can distinguish "no data" from "zero"
- The `member_info` dict (added by `normalize_metrics_identity()`) provides the identity mapping; if absent, identity columns default to empty
- Sprint names with path separators (`\`, `/`) are sanitized in `main.py` before constructing the output filename
