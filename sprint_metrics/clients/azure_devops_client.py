"""Azure DevOps API client for fetching sprint work items."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from azure.devops.v7_1.work_item_tracking.models import Wiql

from sprint_metrics.models import WorkItem

BATCH_SIZE = 200


class AzureDevOpsClient:
    def __init__(self, connection, project: str, category_field: str = "Custom.Category"):
        self._wit = connection.clients.get_work_item_tracking_client()
        self._project = project
        self._category_field = category_field

    def get_sprint_work_items(self, iteration_path: str) -> list[WorkItem]:
        wiql = Wiql(
            query=(
                "SELECT [System.Id] FROM WorkItems "
                f"WHERE [System.IterationPath] = '{iteration_path}' "
                "AND [System.WorkItemType] IN ('User Story', 'Bug', 'Task', 'Feature')"
            )
        )
        result = self._wit.query_by_wiql(wiql, top=1000)
        if not result.work_items:
            return []

        ids = [ref.id for ref in result.work_items]
        fields = [
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

        raw_items = []
        for i in range(0, len(ids), BATCH_SIZE):
            batch = ids[i : i + BATCH_SIZE]
            raw_items.extend(self._wit.get_work_items(batch, fields=fields))

        return [self._to_work_item(raw) for raw in raw_items]

    def get_work_items_by_ids(self, ids: list[int]) -> list[WorkItem]:
        """Fetch specific work items by their IDs."""
        if not ids:
            return []
        fields = [
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
        raw_items = []
        for i in range(0, len(ids), BATCH_SIZE):
            batch = ids[i : i + BATCH_SIZE]
            raw_items.extend(self._wit.get_work_items(batch, fields=fields))
        return [self._to_work_item(raw) for raw in raw_items]

    def _to_work_item(self, raw) -> WorkItem:
        f = raw.fields
        assigned = f.get("System.AssignedTo")
        if isinstance(assigned, dict):
            assigned_to = assigned.get("uniqueName", "")
        elif assigned:
            assigned_to = str(assigned)
        else:
            assigned_to = ""

        tags_str = f.get("System.Tags", "") or ""
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


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt
