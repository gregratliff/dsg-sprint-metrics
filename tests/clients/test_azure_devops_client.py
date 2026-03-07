"""Tests for sprint_metrics.clients.azure_devops_client — Step 3 TDD."""
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from sprint_metrics.clients.azure_devops_client import AzureDevOpsClient
from sprint_metrics.models import WorkItem


def _make_ado_work_item(
    id_,
    title="Task",
    assigned_to="jane.smith@company.com",
    story_points=3.0,
    state="Closed",
    category="strategic",
    tags="",
    activated_date="2026-03-01T00:00:00Z",
    closed_date="2026-03-04T00:00:00Z",
    iteration_path="MyProject\\Sprint 10",
):
    """Build a mock ADO work item object."""
    wi = MagicMock()
    wi.id = id_
    wi.fields = {
        "System.Title": title,
        "System.AssignedTo": {"uniqueName": assigned_to} if assigned_to else None,
        "Microsoft.VSTS.Scheduling.StoryPoints": story_points,
        "System.State": state,
        "Custom.Category": category,
        "System.Tags": tags,
        "Microsoft.VSTS.Common.ActivatedDate": activated_date,
        "Microsoft.VSTS.Common.ClosedDate": closed_date,
        "System.IterationPath": iteration_path,
    }
    return wi


class TestAzureDevOpsClient:
    def _make_client(self, wit_client=None):
        mock_connection = MagicMock()
        mock_wit = wit_client or MagicMock()
        mock_connection.clients.get_work_item_tracking_client.return_value = mock_wit
        return AzureDevOpsClient(
            connection=mock_connection,
            project="MyProject",
            category_field="Custom.Category",
        )

    def test_get_sprint_work_items_returns_work_items(self):
        mock_wit = MagicMock()

        # WIQL returns IDs
        wiql_result = MagicMock()
        wi_ref = MagicMock()
        wi_ref.id = 101
        wiql_result.work_items = [wi_ref]
        mock_wit.query_by_wiql.return_value = wiql_result

        # get_work_items returns full items
        mock_wit.get_work_items.return_value = [
            _make_ado_work_item(101, title="Login feature", story_points=5.0)
        ]

        client = self._make_client(mock_wit)
        items = client.get_sprint_work_items("MyProject\\Sprint 10")

        assert len(items) == 1
        assert isinstance(items[0], WorkItem)
        assert items[0].id == 101
        assert items[0].title == "Login feature"
        assert items[0].story_points == 5.0

    def test_field_mapping(self):
        mock_wit = MagicMock()
        wiql_result = MagicMock()
        wi_ref = MagicMock()
        wi_ref.id = 200
        wiql_result.work_items = [wi_ref]
        mock_wit.query_by_wiql.return_value = wiql_result
        mock_wit.get_work_items.return_value = [
            _make_ado_work_item(
                200,
                title="Fix bug",
                assigned_to="john.doe@company.com",
                story_points=2.0,
                state="Active",
                category="defects",
                tags="rework; missed-ac",
                activated_date="2026-03-02T10:00:00Z",
                closed_date=None,
                iteration_path="MyProject\\Sprint 10",
            )
        ]

        client = self._make_client(mock_wit)
        items = client.get_sprint_work_items("MyProject\\Sprint 10")
        wi = items[0]

        assert wi.assigned_to == "john.doe@company.com"
        assert wi.state == "Active"
        assert wi.category == "defects"
        assert wi.labels == ["rework", "missed-ac"]
        assert wi.activated_date == datetime(2026, 3, 2, 10, 0, 0, tzinfo=UTC)
        assert wi.closed_date is None

    def test_empty_wiql_result(self):
        mock_wit = MagicMock()
        wiql_result = MagicMock()
        wiql_result.work_items = []
        mock_wit.query_by_wiql.return_value = wiql_result

        client = self._make_client(mock_wit)
        items = client.get_sprint_work_items("MyProject\\Sprint 10")

        assert items == []
        mock_wit.get_work_items.assert_not_called()

    def test_tags_parsing(self):
        mock_wit = MagicMock()
        wiql_result = MagicMock()
        wi_ref = MagicMock()
        wi_ref.id = 300
        wiql_result.work_items = [wi_ref]
        mock_wit.query_by_wiql.return_value = wiql_result
        mock_wit.get_work_items.return_value = [
            _make_ado_work_item(300, tags="tag1; tag2; tag3")
        ]

        client = self._make_client(mock_wit)
        items = client.get_sprint_work_items("MyProject\\Sprint 10")

        assert items[0].labels == ["tag1", "tag2", "tag3"]

    def test_empty_tags(self):
        mock_wit = MagicMock()
        wiql_result = MagicMock()
        wi_ref = MagicMock()
        wi_ref.id = 301
        wiql_result.work_items = [wi_ref]
        mock_wit.query_by_wiql.return_value = wiql_result
        mock_wit.get_work_items.return_value = [
            _make_ado_work_item(301, tags="")
        ]

        client = self._make_client(mock_wit)
        items = client.get_sprint_work_items("MyProject\\Sprint 10")

        assert items[0].labels == []

    def test_assigned_to_none(self):
        mock_wit = MagicMock()
        wiql_result = MagicMock()
        wi_ref = MagicMock()
        wi_ref.id = 302
        wiql_result.work_items = [wi_ref]
        mock_wit.query_by_wiql.return_value = wiql_result
        mock_wit.get_work_items.return_value = [
            _make_ado_work_item(302, assigned_to=None)
        ]

        client = self._make_client(mock_wit)
        items = client.get_sprint_work_items("MyProject\\Sprint 10")

        assert items[0].assigned_to == ""

    def test_wiql_query_uses_iteration_path(self):
        mock_wit = MagicMock()
        wiql_result = MagicMock()
        wiql_result.work_items = []
        mock_wit.query_by_wiql.return_value = wiql_result

        client = self._make_client(mock_wit)
        client.get_sprint_work_items("MyProject\\Sprint 10")

        call_args = mock_wit.query_by_wiql.call_args
        wiql_obj = call_args[0][0]
        assert "MyProject\\Sprint 10" in wiql_obj.query

    def test_batches_large_id_lists(self):
        mock_wit = MagicMock()
        wiql_result = MagicMock()
        # 250 work item refs — should be batched into groups of 200
        refs = []
        for i in range(250):
            ref = MagicMock()
            ref.id = i
            refs.append(ref)
        wiql_result.work_items = refs
        mock_wit.query_by_wiql.return_value = wiql_result
        mock_wit.get_work_items.return_value = [
            _make_ado_work_item(i) for i in range(200)
        ]

        client = self._make_client(mock_wit)
        client.get_sprint_work_items("P\\S1")

        assert mock_wit.get_work_items.call_count == 2

    def test_get_work_items_by_ids_skips_invalid_ids(self):
        """Invalid work item IDs are warned about and skipped, not fatal."""
        mock_wit = MagicMock()

        valid_item = _make_ado_work_item(101, title="Valid item")

        # Individual fallback: 101 succeeds, 9999 fails
        def per_item_side_effect(ids, fields=None):
            if ids == [101]:
                return [valid_item]
            if ids == [101, 9999]:
                raise Exception("TF401232: Work item 9999 does not exist")
            raise Exception("TF401232: Work item 9999 does not exist")
        mock_wit.get_work_items.side_effect = per_item_side_effect

        client = self._make_client(mock_wit)
        items = client.get_work_items_by_ids([101, 9999])

        assert len(items) == 1
        assert items[0].id == 101

    def test_get_work_items_by_ids_returns_empty_on_all_invalid(self):
        """All invalid IDs returns empty list with warnings, not crash."""
        mock_wit = MagicMock()

        mock_wit.get_work_items.side_effect = Exception(
            "TF401232: Work item does not exist"
        )

        client = self._make_client(mock_wit)
        items = client.get_work_items_by_ids([9999, 8888])

        assert items == []

    def test_get_sprint_work_items_wraps_wiql_error(self):
        """WIQL query failure is re-raised as RuntimeError with context."""
        mock_wit = MagicMock()
        mock_wit.query_by_wiql.side_effect = Exception("Network timeout")

        client = self._make_client(mock_wit)
        with pytest.raises(RuntimeError, match="Failed to query sprint work items"):
            client.get_sprint_work_items("MyProject\\Sprint 10")

    def test_get_sprint_work_items_asof_includes_date_in_query(self):
        """ASOF query includes the date in the WIQL string."""
        mock_wit = MagicMock()
        wiql_result = MagicMock()
        wiql_result.work_items = []
        mock_wit.query_by_wiql.return_value = wiql_result

        client = self._make_client(mock_wit)
        asof_date = datetime(2026, 3, 8, tzinfo=UTC)
        client.get_sprint_work_items_asof("MyProject\\Sprint 10", asof_date)

        call_args = mock_wit.query_by_wiql.call_args
        wiql_obj = call_args[0][0]
        assert "ASOF" in wiql_obj.query
        assert "2026-03-08" in wiql_obj.query
        assert "MyProject\\Sprint 10" in wiql_obj.query

    def test_get_sprint_work_items_asof_returns_work_items(self):
        """ASOF query returns WorkItem list same as regular query."""
        mock_wit = MagicMock()
        wiql_result = MagicMock()
        wi_ref = MagicMock()
        wi_ref.id = 101
        wiql_result.work_items = [wi_ref]
        mock_wit.query_by_wiql.return_value = wiql_result
        mock_wit.get_work_items.return_value = [
            _make_ado_work_item(101, title="Planned item", story_points=5.0)
        ]

        client = self._make_client(mock_wit)
        items = client.get_sprint_work_items_asof(
            "MyProject\\Sprint 10",
            datetime(2026, 3, 8, tzinfo=UTC),
        )

        assert len(items) == 1
        assert items[0].id == 101
        assert items[0].title == "Planned item"

    def test_get_sprint_work_items_asof_wraps_error(self):
        """ASOF query failure is re-raised as RuntimeError."""
        mock_wit = MagicMock()
        mock_wit.query_by_wiql.side_effect = Exception("Timeout")

        client = self._make_client(mock_wit)
        with pytest.raises(RuntimeError, match="Failed to query sprint work items"):
            client.get_sprint_work_items_asof(
                "MyProject\\Sprint 10",
                datetime(2026, 3, 8, tzinfo=UTC),
            )

    def test_get_sprint_work_items_asof_skips_deleted_items(self):
        """ASOF returns IDs that existed then; deleted items are skipped gracefully."""
        mock_wit = MagicMock()
        wiql_result = MagicMock()
        # ASOF returns two IDs: 101 (still exists) and 999 (deleted since)
        ref1 = MagicMock()
        ref1.id = 101
        ref2 = MagicMock()
        ref2.id = 999
        wiql_result.work_items = [ref1, ref2]
        mock_wit.query_by_wiql.return_value = wiql_result

        valid_item = _make_ado_work_item(101, title="Still exists")

        def per_item_side_effect(ids, fields=None):
            if ids == [101, 999]:
                raise Exception("TF401232: Work item 999 does not exist")
            if ids == [101]:
                return [valid_item]
            raise Exception("TF401232: Work item 999 does not exist")
        mock_wit.get_work_items.side_effect = per_item_side_effect

        client = self._make_client(mock_wit)
        items = client.get_sprint_work_items_asof(
            "MyProject\\Sprint 10",
            datetime(2026, 3, 8, tzinfo=UTC),
        )

        assert len(items) == 1
        assert items[0].id == 101

    def test_get_sprint_work_items_skips_deleted_items(self):
        """Current query also handles deleted items gracefully."""
        mock_wit = MagicMock()
        wiql_result = MagicMock()
        ref1 = MagicMock()
        ref1.id = 101
        ref2 = MagicMock()
        ref2.id = 999
        wiql_result.work_items = [ref1, ref2]
        mock_wit.query_by_wiql.return_value = wiql_result

        valid_item = _make_ado_work_item(101, title="Still exists")

        def per_item_side_effect(ids, fields=None):
            if ids == [101, 999]:
                raise Exception("TF401232: Work item 999 does not exist")
            if ids == [101]:
                return [valid_item]
            raise Exception("TF401232: Work item 999 does not exist")
        mock_wit.get_work_items.side_effect = per_item_side_effect

        client = self._make_client(mock_wit)
        items = client.get_sprint_work_items("MyProject\\Sprint 10")

        assert len(items) == 1
        assert items[0].id == 101
