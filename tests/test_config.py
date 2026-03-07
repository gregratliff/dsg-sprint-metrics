"""Tests for sprint_metrics.config — Step 2 TDD."""
import os
import tempfile
from pathlib import Path

import pytest

from sprint_metrics.config import load_config, ConfigError


VALID_YAML = """\
azure_devops:
  organization: "myorg"
  project: "myproject"
  pat_env_var: "ADO_PAT"
  category_field: "Custom.Category"
  rework_labels:
    - "rework"
    - "missed-ac"

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
"""


class TestLoadConfig:
    def test_load_valid_config(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        cfg = load_config(str(cfg_file))

        assert cfg.azure_devops.organization == "myorg"
        assert cfg.azure_devops.project == "myproject"
        assert cfg.azure_devops.pat_env_var == "ADO_PAT"
        assert cfg.azure_devops.category_field == "Custom.Category"
        assert cfg.azure_devops.rework_labels == ["rework", "missed-ac"]

    def test_github_config(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        cfg = load_config(str(cfg_file))

        assert cfg.github.org == "myorg"
        assert cfg.github.repos == ["repo1", "repo2"]
        assert cfg.github.pat_env_var == "GITHUB_PAT"

    def test_sprint_config(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        cfg = load_config(str(cfg_file))

        assert cfg.sprint.name == "Sprint 23.1"
        assert cfg.sprint.start_date.year == 2026
        assert cfg.sprint.start_date.month == 2
        assert cfg.sprint.start_date.day == 23
        assert cfg.sprint.end_date.year == 2026

    def test_team_members(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        cfg = load_config(str(cfg_file))

        assert len(cfg.team_members) == 2
        assert cfg.team_members[0].name == "Jane Smith"
        assert cfg.team_members[0].github_username == "janesmith"
        assert cfg.team_members[0].ado_identity == "jane.smith@company.com"

    def test_categories(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        cfg = load_config(str(cfg_file))

        assert cfg.categories == ["strategic", "tech_health", "defects"]

    def test_missing_required_field_raises(self, tmp_path):
        bad_yaml = "azure_devops:\n  organization: myorg\n"
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(bad_yaml)

        with pytest.raises(ConfigError):
            load_config(str(cfg_file))

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path.yaml")

    def test_default_category_field(self, tmp_path):
        yaml_no_cat_field = VALID_YAML.replace(
            '  category_field: "Custom.Category"\n', ""
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_no_cat_field)
        cfg = load_config(str(cfg_file))

        assert cfg.azure_devops.category_field == "Custom.Category"

    def test_default_rework_labels(self, tmp_path):
        yaml_no_rework = VALID_YAML.replace(
            '  rework_labels:\n    - "rework"\n    - "missed-ac"\n', ""
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_no_rework)
        cfg = load_config(str(cfg_file))

        assert cfg.azure_devops.rework_labels == []

    def test_github_username_to_name_lookup(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        cfg = load_config(str(cfg_file))

        assert cfg.get_member_by_github("janesmith").name == "Jane Smith"
        assert cfg.get_member_by_github("unknown") is None

    def test_ado_identity_to_name_lookup(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        cfg = load_config(str(cfg_file))

        assert cfg.get_member_by_ado("jane.smith@company.com").name == "Jane Smith"
        assert cfg.get_member_by_ado("unknown@x.com") is None

    def test_pr_exclude_patterns_parsed(self, tmp_path):
        yaml_with_patterns = VALID_YAML.replace(
            '  pat_env_var: "GITHUB_PAT"',
            '  pat_env_var: "GITHUB_PAT"\n'
            '  pr_exclude_patterns:\n'
            '    - "^(production|pentest|master) deploy"\n'
            '    - "^develop -> master"',
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_with_patterns)
        cfg = load_config(str(cfg_file))

        assert cfg.github.pr_exclude_patterns == [
            "^(production|pentest|master) deploy",
            "^develop -> master",
        ]

    def test_pr_exclude_patterns_defaults_empty(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        cfg = load_config(str(cfg_file))

        assert cfg.github.pr_exclude_patterns == []

    def test_planning_offset_days_default(self, tmp_path):
        """planning_offset_days defaults to 7 when not specified."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(VALID_YAML)
        cfg = load_config(str(cfg_file))

        assert cfg.sprint.planning_offset_days == 7

    def test_planning_offset_days_explicit(self, tmp_path):
        """Explicit planning_offset_days is respected."""
        yaml_with_offset = VALID_YAML.replace(
            '  end_date: "2026-03-06"',
            '  end_date: "2026-03-06"\n  planning_offset_days: 5',
        )
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml_with_offset)
        cfg = load_config(str(cfg_file))

        assert cfg.sprint.planning_offset_days == 5
