"""Configuration loading and validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import yaml


class ConfigError(Exception):
    pass


@dataclass
class AzureDevOpsConfig:
    organization: str
    project: str
    pat_env_var: str
    category_field: str = "Custom.Category"
    rework_labels: list[str] = field(default_factory=list)


@dataclass
class GitHubConfig:
    org: str
    repos: list[str]
    pat_env_var: str
    pr_exclude_patterns: list[str] = field(default_factory=list)


@dataclass
class SprintConfig:
    name: str
    start_date: datetime
    end_date: datetime
    planning_offset_days: int = 7


@dataclass
class TeamMember:
    name: str
    github_username: str
    ado_identity: str


@dataclass
class Config:
    azure_devops: AzureDevOpsConfig
    github: GitHubConfig
    sprint: SprintConfig
    team_members: list[TeamMember]
    categories: list[str]

    def get_member_by_github(self, username: str) -> Optional[TeamMember]:
        for m in self.team_members:
            if m.github_username == username:
                return m
        return None

    def get_member_by_ado(self, identity: str) -> Optional[TeamMember]:
        for m in self.team_members:
            if m.ado_identity == identity:
                return m
        return None


def _require(data: dict, key: str, context: str = "") -> object:
    if key not in data:
        loc = f" in {context}" if context else ""
        raise ConfigError(f"Missing required field '{key}'{loc}")
    return data[key]


def load_config(path: str) -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ConfigError("Config file must be a YAML mapping")

    # Azure DevOps
    ado_raw = _require(raw, "azure_devops")
    ado = AzureDevOpsConfig(
        organization=_require(ado_raw, "organization", "azure_devops"),
        project=_require(ado_raw, "project", "azure_devops"),
        pat_env_var=_require(ado_raw, "pat_env_var", "azure_devops"),
        category_field=ado_raw.get("category_field", "Custom.Category"),
        rework_labels=ado_raw.get("rework_labels", []),
    )

    # GitHub
    gh_raw = _require(raw, "github")
    gh = GitHubConfig(
        org=_require(gh_raw, "org", "github"),
        repos=_require(gh_raw, "repos", "github"),
        pat_env_var=_require(gh_raw, "pat_env_var", "github"),
        pr_exclude_patterns=gh_raw.get("pr_exclude_patterns", []),
    )

    # Sprint
    sprint_raw = _require(raw, "sprint")
    sprint = SprintConfig(
        name=_require(sprint_raw, "name", "sprint"),
        start_date=datetime.fromisoformat(
            str(_require(sprint_raw, "start_date", "sprint"))
        ),
        end_date=datetime.fromisoformat(
            str(_require(sprint_raw, "end_date", "sprint"))
        ),
        planning_offset_days=int(sprint_raw.get("planning_offset_days", 7)),
    )

    # Team members
    members_raw = _require(raw, "team_members")
    members = [
        TeamMember(
            name=_require(m, "name", "team_members"),
            github_username=_require(m, "github_username", "team_members"),
            ado_identity=_require(m, "ado_identity", "team_members"),
        )
        for m in members_raw
    ]

    # Categories
    categories = _require(raw, "categories")

    return Config(
        azure_devops=ado,
        github=gh,
        sprint=sprint,
        team_members=members,
        categories=categories,
    )
