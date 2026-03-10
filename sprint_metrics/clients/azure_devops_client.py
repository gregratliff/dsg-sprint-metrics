"""Azure DevOps API client for fetching sprint work items."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from azure.devops.v7_1.work_item_tracking.models import Wiql

from sprint_metrics.models import WorkItem

BATCH_SIZE = 200

logger = logging.getLogger(__name__)


class AzureDevOpsClient:
    def __init__(self, connection: Any, project: str, category_field: str = "Custom.Category") -> None:
        self._wit: Any = connection.clients.get_work_item_tracking_client()
        self._project = project
        self._category_field = category_field

    @property
    def _fields(self) -> list[str]:
        return [
            "System.Title",
            "System.AssignedTo",
            "Microsoft.VSTS.Scheduling.StoryPoints",
            "System.State",
            self._category_field,
            "System.Tags",
            "Microsoft.VSTS.Common.ActivatedDate",
            "Microsoft.VSTS.Common.ClosedDate",
            "System.IterationPath",
        ]

    def _fetch_work_items_resilient(self, ids: list[int]) -> list[Any]:
        """Fetch work items with batch-then-individual fallback for bad IDs."""
        raw_items: list[Any] = []
        for i in range(0, len(ids), BATCH_SIZE):
            batch = ids[i : i + BATCH_SIZE]
            try:
                raw_items.extend(self._wit.get_work_items(batch, fields=self._fields))
            except Exception:
                for wid in batch:
                    try:
                        raw_items.extend(
                            self._wit.get_work_items([wid], fields=self._fields)
                        )
                    except Exception:
                        logger.warning(
                            "Work item %d not found or inaccessible — skipping", wid
                        )
        return raw_items

    def get_iteration_dates(self, iteration_path: str) -> tuple[datetime, datetime]:
        """Fetch start and finish dates for an iteration from the classification node."""
        try:
            node = self._wit.get_classification_node(
                project=self._project,
                structure_group="iterations",
                path=iteration_path,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to fetch iteration dates for '{iteration_path}': {exc}"
            ) from exc

        attrs: dict[str, str] | None = node.attributes
        if not attrs or "startDate" not in attrs or "finishDate" not in attrs:
            raise RuntimeError(
                f"No date attributes found on iteration '{iteration_path}'"
            )

        start = _parse_date(attrs["startDate"])
        end = _parse_date(attrs["finishDate"])
        if start is None or end is None:
            raise RuntimeError(
                f"Could not parse dates for iteration '{iteration_path}'"
            )
        return start, end

    def get_sprint_work_items(self, iteration_path: str) -> list[WorkItem]:
        wiql = Wiql(
            query=(
                "SELECT [System.Id] FROM WorkItems "
                f"WHERE [System.IterationPath] = '{iteration_path}' "
                "AND [System.WorkItemType] IN ('User Story', 'Bug', 'Task', 'Feature')"
            )
        )
        try:
            result = self._wit.query_by_wiql(wiql, top=1000)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to query sprint work items for '{iteration_path}': {exc}"
            ) from exc
        if not result.work_items:
            return []

        ids = [ref.id for ref in result.work_items]
        return [self._to_work_item(raw) for raw in self._fetch_work_items_resilient(ids)]

    def get_sprint_work_items_asof(
        self, iteration_path: str, asof_date: datetime,
    ) -> list[WorkItem]:
        """Query sprint membership as of a specific date using WIQL ASOF."""
        asof_str = asof_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        wiql = Wiql(
            query=(
                "SELECT [System.Id] FROM WorkItems "
                f"WHERE [System.IterationPath] = '{iteration_path}' "
                "AND [System.WorkItemType] IN ('User Story', 'Bug', 'Task', 'Feature') "
                f"ASOF '{asof_str}'"
            )
        )
        try:
            result = self._wit.query_by_wiql(wiql, top=1000)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to query sprint work items for '{iteration_path}' "
                f"as of {asof_str}: {exc}"
            ) from exc
        if not result.work_items:
            return []

        ids = [ref.id for ref in result.work_items]
        return [self._to_work_item(raw) for raw in self._fetch_work_items_resilient(ids)]

    def get_work_items_by_ids(self, ids: list[int]) -> list[WorkItem]:
        """Fetch specific work items by their IDs."""
        if not ids:
            return []
        return [self._to_work_item(raw) for raw in self._fetch_work_items_resilient(ids)]

    def _to_work_item(self, raw: Any) -> WorkItem:
        f: dict[str, Any] = raw.fields
        assigned = f.get("System.AssignedTo")
        if isinstance(assigned, dict):
            assigned_to = assigned.get("uniqueName", "")
        elif assigned:
            assigned_to = str(assigned)
        else:
            assigned_to = ""

        tags_str: str = f.get("System.Tags", "") or ""
        labels = [t.strip() for t in tags_str.split(";") if t.strip()]

        return WorkItem(
            id=raw.id,
            title=f.get("System.Title", ""),
            assigned_to=assigned_to,
            story_points=f.get("Microsoft.VSTS.Scheduling.StoryPoints"),
            state=f.get("System.State", ""),
            category=f.get(self._category_field),
            labels=labels,
            activated_date=_parse_date(f.get("Microsoft.VSTS.Common.ActivatedDate")),
            closed_date=_parse_date(f.get("Microsoft.VSTS.Common.ClosedDate")),
            iteration_path=f.get("System.IterationPath", ""),
        )


def _parse_date(value: str | datetime | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt
