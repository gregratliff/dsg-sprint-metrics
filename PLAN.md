# Sprint Metrics Tool — Implementation Plan

## Overview
A Python CLI tool that collects sprint metrics from Azure DevOps (work items) and GitHub (pull requests), calculates key metrics for individuals and teams, and outputs CSV reports.

## Architecture

```
sprint_metrics/
├── __init__.py
├── main.py                    # CLI entrypoint (argparse)
├── config.py                  # Config loading & validation (YAML)
├── models.py                  # Data classes: WorkItem, PullRequest, SprintMetrics
├── clients/
│   ├── __init__.py
│   ├── azure_devops_client.py # ADO API wrapper
│   └── github_client.py       # GitHub API wrapper
├── metrics/
│   ├── __init__.py
│   ├── velocity.py            # Planned vs delivered story points
│   ├── cycle_time.py          # Work item cycle time (Activated → Closed)
│   ├── pr_cycle_time.py       # PR cycle time (Opened → Merged)
│   ├── rework.py              # Rework detection via configurable labels
│   └── category_breakdown.py  # Points by work category
├── reports/
│   ├── __init__.py
│   └── csv_writer.py          # CSV output generation
config.example.yaml            # Example configuration
requirements.txt
tests/
├── __init__.py
├── conftest.py                # Shared fixtures
├── test_config.py
├── test_models.py
├── clients/
│   ├── __init__.py
│   ├── test_azure_devops_client.py
│   └── test_github_client.py
├── metrics/
│   ├── __init__.py
│   ├── test_velocity.py
│   ├── test_cycle_time.py
│   ├── test_pr_cycle_time.py
│   ├── test_rework.py
│   └── test_category_breakdown.py
└── reports/
    ├── __init__.py
    └── test_csv_writer.py
```

## Key Design Decisions

- **PR ↔ Work Item linking**: Parse `AB#12345` patterns from commit messages
- **Category field**: Use ADO custom field "Category" (under Classification header); reference name likely `Custom.Category` — will need to be configurable
- **Cycle time**: Work item = `Activated → Closed` date diff. PR = `created_at → merged_at` date diff.
- **Rework labels**: Configurable list in YAML (e.g., `rework`, `missed-ac`, `qa-rejected`)
- **All API clients**: Accept injected dependencies so tests use mocks, never real APIs
- **Category list**: Configurable in YAML (strategic, tech_health, defects, etc.)

## TDD Implementation Steps

Each step follows: **write failing test → write production code → green → refactor**.

---

### Phase 1: Foundation (Models & Config)

#### Step 1: Data Models (`models.py`)
**Test first:** `tests/test_models.py`
- Test `WorkItem` dataclass creation with fields: id, title, assigned_to, story_points, state, category, tags/labels, activated_date, closed_date, iteration_path
- Test `PullRequest` dataclass creation with fields: id, number, title, author, created_at, merged_at, closed_at, repo, commit_messages, linked_work_item_ids
- Test `SprintInfo` dataclass: name, start_date, end_date, team
- Test `WorkItem.cycle_time_days` computed property (returns None if not yet closed)
- Test `PullRequest.cycle_time_hours` computed property (returns None if not merged)
- Test `PullRequest.extract_work_item_ids()` — parses AB#12345 from commit messages

#### Step 2: Config Loading (`config.py`)
**Test first:** `tests/test_config.py`
- Test loading a valid YAML config with all required fields
- Test validation: missing required fields raise clear errors
- Test defaults: optional fields have sensible defaults
- Test team member mapping: GitHub username ↔ ADO identity ↔ display name
- Test rework labels list parsing
- Test category field name configuration
- Test sprint date range parsing

Config structure:
```yaml
azure_devops:
  organization: "myorg"
  project: "myproject"
  pat_env_var: "ADO_PAT"            # env var name holding the PAT
  category_field: "Custom.Category"  # ADO field reference name
  rework_labels:
    - "rework"
    - "missed-ac"
    - "qa-rejected"

github:
  org: "myorg"
  repos:
    - "repo1"
    - "repo2"
  pat_env_var: "GITHUB_PAT"

sprint:
  name: "Sprint 23.1"
  start_date: "2026-02-23"
  end_date: "2026-03-06"

team_members:
  - name: "Jane Smith"
    github_username: "janesmith"
    ado_identity: "jane.smith@company.com"
  - name: "John Doe"
    github_username: "johndoe"
    ado_identity: "john.doe@company.com"

categories:
  - "strategic"
  - "tech_health"
  - "defects"
  - "operational"
```

---

### Phase 2: API Clients (with mocked dependencies)

#### Step 3: Azure DevOps Client (`clients/azure_devops_client.py`)
**Test first:** `tests/clients/test_azure_devops_client.py`

All tests mock the `azure.devops.v7_1` SDK connection — no real API calls.

- Test `get_sprint_work_items(iteration_path)` — returns list of `WorkItem` models
  - Mock WIQL query: `SELECT [System.Id] FROM WorkItems WHERE [System.IterationPath] = '...'`
  - Mock `get_work_item()` calls to build WorkItem models
  - Test field mapping: ADO fields → WorkItem dataclass
- Test `get_work_item_updates(work_item_id)` — returns state change history
  - Used to determine ActivatedDate/ClosedDate when not directly available
- Test error handling: connection failure, auth failure, no results
- Test filtering by team members (ADO identity match)

#### Step 4: GitHub Client (`clients/github_client.py`)
**Test first:** `tests/clients/test_github_client.py`

All tests mock the `github.Github` class — no real API calls.

- Test `get_pull_requests(repo, start_date, end_date)` — returns list of `PullRequest` models
  - Mock `repo.get_pulls(state='all')` filtered by date range
  - Test field mapping: PyGithub PR object → PullRequest dataclass
- Test `get_pr_commits(pr)` — returns commit messages for AB# extraction
- Test filtering by team members (GitHub username match)
- Test pagination handling (multiple pages of PRs)
- Test error handling: auth failure, repo not found

---

### Phase 3: Metrics Calculators

#### Step 5: Velocity (`metrics/velocity.py`)
**Test first:** `tests/metrics/test_velocity.py`
- Test `calculate_velocity(work_items, sprint_info)`:
  - Planned points: sum of story_points for items in the sprint at sprint start
  - Delivered points: sum of story_points for items closed during the sprint
  - Returns per-person and team-level velocity
- Test with zero story points
- Test with items that have no story points (None/0 — should be excluded or counted as 0)
- Test team aggregation

#### Step 6: Cycle Time (`metrics/cycle_time.py`)
**Test first:** `tests/metrics/test_cycle_time.py`
- Test `calculate_cycle_times(work_items)`:
  - Per-item cycle time in days (activated → closed)
  - Per-person average cycle time
  - Team average cycle time
- Test items with no activated date (should be excluded)
- Test items not yet closed (should be excluded from averages)
- Test median and average calculations

#### Step 7: PR Cycle Time (`metrics/pr_cycle_time.py`)
**Test first:** `tests/metrics/test_pr_cycle_time.py`
- Test `calculate_pr_cycle_times(pull_requests)`:
  - Per-PR cycle time in hours (opened → merged)
  - Per-person average PR cycle time
  - Team average PR cycle time
- Test unmerged PRs (excluded from cycle time)
- Test PRs with very short or very long cycle times

#### Step 8: Rework (`metrics/rework.py`)
**Test first:** `tests/metrics/test_rework.py`
- Test `calculate_rework(work_items, rework_labels)`:
  - Count of items with any rework label
  - Rework points (sum of story points on rework items)
  - Rework rate (rework items / total items)
  - Per-person rework counts
  - Team rework summary
- Test case-insensitive label matching
- Test items with multiple rework labels (counted once)
- Test zero rework scenario

#### Step 9: Category Breakdown (`metrics/category_breakdown.py`)
**Test first:** `tests/metrics/test_category_breakdown.py`
- Test `calculate_category_breakdown(work_items, categories)`:
  - Points per category
  - Items per category
  - Per-person category breakdown
  - Uncategorized items handling
- Test items with unknown categories (grouped as "other")
- Test empty categories

---

### Phase 4: Reporting

#### Step 10: CSV Writer (`reports/csv_writer.py`)
**Test first:** `tests/reports/test_csv_writer.py`
- Test `write_sprint_report(metrics, output_path)`:
  - Generates a CSV with sections for each metric type
  - Includes individual and team rows
  - Test file creation and content validation
- Test `write_velocity_csv(velocity_data, output_path)` — dedicated velocity report
- Test `write_summary_csv(all_metrics, output_path)` — one-row-per-person summary
- Test output formatting (decimal places, date formats)

---

### Phase 5: CLI & Integration

#### Step 11: CLI Entrypoint (`main.py`)
**Test first:** `tests/test_main.py` (integration-style, all clients mocked)
- Test argument parsing: `--config`, `--output-dir`, `--sprint` (optional override)
- Test full pipeline: config → clients → metrics → CSV output
- Test error messaging for missing config, bad auth env vars
- Test `--dry-run` flag (validates config without calling APIs)

---

## Dependencies

```
# requirements.txt
azure-devops>=7.1.0b4
PyGithub>=2.1.0
PyYAML>=6.0
python-dateutil>=2.8
pytest>=7.0
pytest-cov>=4.0
```

## Authentication
- Both APIs use Personal Access Tokens (PATs)
- PATs are read from environment variables (names configured in YAML)
- Never stored in config files

## Execution Flow
```
1. Load config.yaml
2. Read PATs from environment variables
3. Initialize ADO and GitHub clients
4. Fetch work items from ADO for the sprint iteration
5. Fetch PRs from GitHub for the sprint date range
6. Link PRs to work items via AB# in commit messages
7. Calculate all metrics
8. Write CSV report(s)
```

## Build Order Summary
| Step | Component | Test File | Production File |
|------|-----------|-----------|-----------------|
| 1 | Models | test_models.py | models.py |
| 2 | Config | test_config.py | config.py |
| 3 | ADO Client | test_azure_devops_client.py | azure_devops_client.py |
| 4 | GitHub Client | test_github_client.py | github_client.py |
| 5 | Velocity | test_velocity.py | velocity.py |
| 6 | Cycle Time | test_cycle_time.py | cycle_time.py |
| 7 | PR Cycle Time | test_pr_cycle_time.py | pr_cycle_time.py |
| 8 | Rework | test_rework.py | rework.py |
| 9 | Categories | test_category_breakdown.py | category_breakdown.py |
| 10 | CSV Writer | test_csv_writer.py | csv_writer.py |
| 11 | CLI | test_main.py | main.py |
