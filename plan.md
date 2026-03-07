# Sprint Metrics Enhancement Plan

All changes follow RED-GREEN-REFACTOR TDD workflow: write failing tests first, implement to make them pass, then refactor.

---

## 1. Combine ADO + GitHub Identity into Single Rows

**Problem:** Velocity/cycle_time/rework metrics key by `wi.assigned_to` (ADO email), while pr_cycle_time keys by `pr.author` (GitHub username). The CSV writer collects all unique keys, so "jane.smith@company.com" and "janesmith" appear as separate rows.

**Approach:**
- Add an identity resolution step in `main.py` (between metric calculation and CSV writing) that normalizes all metric dicts to use the `TeamMember.name` as the canonical key
- Add `ado_identity` and `github_username` as new CSV columns so both raw identities are visible
- The `member` column becomes the display name from config

**Files to change:**
- `tests/test_csv_writer.py` — RED: test that output has `ado_identity` and `github_username` columns, and combined rows
- `sprint_metrics/reports/csv_writer.py` — GREEN: add the new columns
- `tests/test_main.py` — RED: test that `run()` produces a single row per team member with merged metrics
- `sprint_metrics/main.py` — GREEN: add identity normalization function that remaps metric dict keys using `config.team_members`

---

## 2. Filter Stats to Configured Team Members Only

**Problem:** Multiple teams share the same ADO board. Work items assigned to non-team members (other teams) get included in the report.

**Approach:**
- Filter work items after fetching: only keep items where `assigned_to` matches a configured `team_member.ado_identity`
- GitHub client already accepts `team_usernames` — ensure `main.py` passes it
- The identity normalization from step 1 naturally drops unknown users since they won't have a TeamMember mapping

**Files to change:**
- `tests/test_main.py` — RED: test that work items from non-team members are excluded from the report
- `sprint_metrics/main.py` — GREEN: filter work items to team members; pass `team_usernames` to GitHub client
- Verify existing GitHub client filtering is already wired up

---

## 3. Exclude Deployment PRs from Stats

**Problem:** Deployment PRs (e.g., "production deploy 2026-02-26", "develop -> master 2026-02-26") are merged quickly and don't go through normal review. Including them skews PR cycle time metrics.

**Approach — Configurable regex exclude patterns in config:**
```yaml
github:
  pr_exclude_patterns:
    - "^(production|pentest|master) deploy"
    - "^develop -> master"
```
- Add `pr_exclude_patterns: list[str]` to the GitHub config section
- Filter PRs after fetching: exclude any PR whose title matches any pattern
- This gives each team lead control over what's excluded for their team

**Files to change:**
- `tests/test_config.py` — RED: test parsing `pr_exclude_patterns` from YAML
- `sprint_metrics/config.py` — GREEN: add `pr_exclude_patterns` field with default `[]`
- `tests/test_github_client.py` or `tests/test_main.py` — RED: test that PRs matching patterns are excluded
- `sprint_metrics/main.py` (or a filtering utility) — GREEN: apply pattern filtering after PR fetch
- Update `config.example.yaml` with the new field

---

## Execution Order

Since #1 (identity normalization) and #2 (team filtering) are tightly coupled — filtering to team members and then normalizing keys — they should be implemented together. #3 (deployment PR exclusion) is independent.

### Step-by-step:

1. **RED** — Write tests for `pr_exclude_patterns` config parsing
2. **GREEN** — Add `pr_exclude_patterns` to config model
3. **RED** — Write tests for deployment PR filtering
4. **GREEN** — Implement PR filtering by title pattern
5. **RED** — Write tests for team-member-only filtering (work items from other teams excluded)
6. **GREEN** — Filter work items to configured team members in `main.py`
7. **RED** — Write tests for identity normalization (single row per member, ado_identity + github_username columns)
8. **GREEN** — Implement identity normalization and update CSV writer
9. **REFACTOR** — Clean up, ensure all tests pass, review for simplicity
