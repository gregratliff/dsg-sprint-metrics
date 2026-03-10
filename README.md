# Sprint Metrics Tool

A command-line tool that collects sprint metrics from Azure DevOps (ADO) and GitHub, then generates a CSV report with per-developer and team-level performance data. Designed for engineering managers and scrum masters who need sprint-over-sprint visibility across both platforms.

## What It Does

The tool runs a pipeline that:

1. **Fetches work items** from Azure DevOps using WIQL queries with historical snapshots (ASOF) to capture what was planned vs. what was delivered
2. **Fetches pull requests** from GitHub filtered by merge date within the sprint window
3. **Classifies scope changes** — items committed at planning, added mid-sprint, removed, or carried over to the next sprint
4. **Calculates metrics** — velocity, cycle time, PR cycle time, rework rate, and category breakdown
5. **Writes a CSV report** with one row per team member plus a TEAM aggregate row

### Metrics Collected

| Metric | Source | Description |
|--------|--------|-------------|
| **Velocity** | ADO | Planned points, delivered points, delivery rate, scope added/removed/carried over, commitment reliability |
| **Cycle Time** | ADO | Average and median days from Activated to Closed (excludes removed/carried-over items) |
| **PR Cycle Time** | GitHub | Average and median hours from PR creation to merge |
| **Rework** | ADO | Count and points of items tagged with rework labels (e.g., `rework`, `missed-ac`, `qa-rejected`) |
| **Category Breakdown** | ADO | Points and count per work category (e.g., strategic, tech_health, defects) |

## Project Structure

```
sprint_metrics/
  main.py              # CLI entrypoint and pipeline orchestration
  config.py            # Config loading and validation
  models.py            # Domain model dataclasses (WorkItem, PullRequest)
  clients/
    azure_devops_client.py   # ADO WIQL queries and work item fetching
    github_client.py         # GitHub PR fetching with merge-date filtering
  metrics/
    velocity.py              # Scope-aware velocity calculation
    cycle_time.py            # Work item cycle time (days)
    pr_cycle_time.py         # Pull request cycle time (hours)
    rework.py                # Rework detection by labels
    category_breakdown.py    # Per-category point breakdown
  reports/
    csv_writer.py            # CSV report output
tests/                       # Mirrors source structure, 95%+ coverage
```

## Prerequisites

- Python 3.11 or later
- Access to Azure DevOps (with a Personal Access Token)
- Access to GitHub (with a Personal Access Token)

## Environment Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd sprint-metrics
pip install -r requirements.txt
```

### 2. Generate Personal Access Tokens (PATs)

#### Azure DevOps PAT

1. Go to `https://dev.azure.com/{your-org}/_usersSettings/tokens`
2. Click **New Token**
3. Set a descriptive name (e.g., "Sprint Metrics Tool")
4. Set the expiration (recommend 90 days, set a calendar reminder to rotate)
5. Under **Scopes**, select:
   - **Work Items** → Read
6. Click **Create** and copy the token immediately (it won't be shown again)

#### GitHub PAT

1. Go to `https://github.com/settings/tokens` (or Fine-grained tokens for more control)
2. Click **Generate new token** → **Generate new token (classic)**
3. Set a descriptive name and expiration
4. Under **Scopes**, select:
   - `repo` (Full control of private repositories) — needed to read PRs and commits from private repos
   - For public repos only, `public_repo` is sufficient
5. Click **Generate token** and copy it immediately

### 3. Set environment variables

Export the PATs as environment variables. The variable names must match what's in your config file:

```bash
export ADO_PAT="your-azure-devops-pat-here"
export GITHUB_PAT="your-github-pat-here"
```

For persistent setup, add these to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.) or use a secrets manager.

**Security note:** Never commit PATs to source control. The tool reads them exclusively from environment variables — the config file only stores the _name_ of the environment variable, not the token itself.

## Configuration

Create a YAML config file (see `config.example.yaml` for a complete template):

```yaml
azure_devops:
  organization: "your-org"
  project: "your-project"
  pat_env_var: "ADO_PAT"                # Name of the env var holding the ADO PAT
  category_field: "Custom.Category"     # ADO field reference name for work category
  rework_labels:                        # Tags that QA applies to rework items
    - "rework"
    - "missed-ac"
    - "qa-rejected"

github:
  org: "your-github-org"
  repos:
    - "repo1"
    - "repo2"
  pat_env_var: "GITHUB_PAT"            # Name of the env var holding the GitHub PAT
  pr_exclude_patterns:                  # Regex patterns to exclude PRs by title
    - "^(production|pentest|master) deploy"
    - "^develop -> master"

sprint:
  stem: "26\\Q1 2026"                  # Parent iteration path levels (above sprint name)
  name: "Sprint 26.3.1"                # Sprint name (leaf level)
  start_date: "2026-03-01"
  end_date: "2026-03-14"
  planning_offset_days: 7              # Days after start_date before planning snapshot

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

### Understanding Sprint Iteration Paths

Azure DevOps iterations are hierarchical. The tool constructs the full iteration path as:

```
{project}\{stem}\{name}
```

For example, with `project: "MyProject"`, `stem: "26\Q1 2026"`, and `name: "Sprint 26.3.1"`, the iteration path becomes:

```
MyProject\26\Q1 2026\Sprint 26.3.1
```

The **stem** stays constant across sprints within the same quarter/year. Only the **name** changes each sprint. You can override the sprint name from the command line with `--sprint-name` so you don't have to edit the config file every sprint.

### Finding Your Iteration Path

To find the correct stem and name for your project:

1. In Azure DevOps, go to **Project Settings** → **Boards** → **Project configuration** → **Iterations**
2. Expand the iteration tree to find your current sprint
3. The path shown in the tree is what you split into stem and name

### Identity Mapping

Each team member entry maps three identity systems together:
- `name` — Display name used in the CSV report
- `github_username` — GitHub login (used to match PR authors)
- `ado_identity` — ADO identity, typically the email address shown on work items (e.g., `jane.smith@company.com`)

To find a team member's ADO identity, look at any work item assigned to them — the `Assigned To` field shows the identity string the API returns.

## Running the Tool

### Dry run (validate config and connectivity)

```bash
python -m sprint_metrics.main --config config.yaml --dry-run
```

This validates the config file, checks that the required PAT environment variables are set, and exits without making any API calls. Use this to verify your setup before running the full pipeline.

**Expected output:**
```
INFO: Config validated: sprint='Sprint 26.3.1', 6 team members, 4 categories
```

### Full run

```bash
python -m sprint_metrics.main --config config.yaml --output-dir ./reports
```

### Override sprint name from CLI

```bash
python -m sprint_metrics.main --config config.yaml --sprint-name "Sprint 26.3.2"
```

This overrides the `sprint.name` value from the config file, so you can reuse the same config file across sprints by only changing the command-line argument.

### Command-Line Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--config` | Yes | — | Path to the YAML config file |
| `--output-dir` | No | `.` (current directory) | Directory where the CSV report is written |
| `--dry-run` | No | `false` | Validate config without calling APIs |
| `--sprint-name` | No | Value from config | Override `sprint.name` from the config file |

## Understanding the Output

### CSV Report

The output is a CSV file named `{sprint_name}_report.csv` (with path separators replaced by underscores). For example: `Sprint_26.3.1_report.csv`.

**Columns:**

| Column | Description |
|--------|-------------|
| `sprint` | Sprint name |
| `member` | Team member display name (or `TEAM` for aggregate row) |
| `ado_identity` | ADO email identity |
| `github_username` | GitHub login |
| `planned_points` | Story points committed at planning |
| `delivered_points` | Story points completed (Closed/Resolved) |
| `delivery_rate` | `delivered / planned` as a decimal |
| `avg_cycle_time_days` | Mean days from Activated to Closed |
| `median_cycle_time_days` | Median days from Activated to Closed |
| `cycle_time_count` | Number of items with cycle time data |
| `avg_pr_cycle_time_hours` | Mean hours from PR creation to merge |
| `median_pr_cycle_time_hours` | Median hours from PR creation to merge |
| `pr_count` | Number of merged PRs |
| `rework_count` | Items tagged with rework labels |
| `rework_points` | Story points of rework items |
| `rework_rate` | `rework_count / total_count` |
| `{category}_points` | Points in each configured category |
| `{category}_count` | Item count in each configured category |

### Console Output During a Run

A typical run produces log output like this:

```
INFO: Fetching planning snapshot (as of 2026-03-08)...
INFO: Planning snapshot: 24 work items
INFO: Fetching end-of-sprint snapshot (as of 2026-03-14)...
INFO: End-of-sprint snapshot: 26 work items
INFO: Fetching current state of 2 items removed from sprint...
INFO: Work item 12345 (Login fix) carried over to MyProject\26\Q1 2026\Sprint 26.3.2 — 3.0 points
WARNING: Work item 12346 (Dashboard redesign) removed from sprint — 5.0 points descoped
INFO: Work item 12350 (New onboarding flow) added mid-sprint — 8.0 points
INFO: Fetching PRs from myorg/repo1...
INFO: Fetching PRs from myorg/repo2...
INFO: Total: 18 PRs across 2 repos
INFO: Excluded 3 PRs matching exclude patterns
WARNING: PR #142 (johndoe) has no work item reference
INFO: Report written to ./reports/Sprint_26.3.1_report.csv
```

### Warnings and Edge Cases

| Warning | Meaning | Impact |
|---------|---------|--------|
| `Work item N removed from sprint — X points descoped` | An item was in the planning snapshot but not at sprint end, and it was moved to the backlog (not another sprint) | Counted as scope removed in velocity metrics |
| `PR #N (author) has no work item reference` | A merged PR has no `AB#12345` pattern in its title, body, or commit messages | The PR is still counted for PR cycle time, but it won't be linked to a work item |
| `Work item N not found — referenced by PR #M (author)` | A PR references a work item ID that doesn't exist in ADO | The invalid reference is skipped; other metrics are unaffected |
| `Failed to fetch PRs from org/repo — skipping this repo` | A GitHub repo is inaccessible (permissions, deleted, wrong name) | PRs from that repo are excluded; PRs from other repos are still collected |
| `planning_offset_days (N) exceeds sprint duration — clamping to end_date` | The planning offset is longer than the sprint itself | The planning snapshot uses the end date instead |

## Development Setup

### Install dev dependencies

```bash
pip install -r requirements.txt
```

This includes runtime dependencies (`azure-devops`, `PyGithub`, `PyYAML`) and dev tools (`pytest`, `pytest-cov`, `mypy`, `ruff`, `pip-audit`).

### Run tests

```bash
python -m pytest tests/
```

Coverage is enforced at 80% minimum (currently 95%+). The `--cov-fail-under=80` flag is configured in `pyproject.toml`.

### Type checking

```bash
python -m mypy sprint_metrics/ --strict
```

All production code must pass `mypy --strict`. Third-party libraries without type stubs (`azure-devops`, `PyGithub`) use `ignore_missing_imports` in `pyproject.toml`.

### Linting

```bash
python -m ruff check sprint_metrics/ tests/
```

Enforces pycodestyle, pyflakes, isort, bugbear, bandit security checks, and more. See `pyproject.toml` for the full rule set.

### Development workflow

This project follows strict TDD (Red-Green-Refactor). See `CLAUDE.md` for the full workflow, quality gates, and coding standards.
