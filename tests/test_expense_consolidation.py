import unittest
from decimal import Decimal
from unittest.mock import patch

from database.sheets_repository import (
    get_combined_person_expenses,
    list_person_expense_summaries,
)


class PersonExpenseConsolidationRepositoryTests(unittest.TestCase):
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/test123/edit"

    def setUp(self):
        self.rows = {
            "Participants": [
                {
                    "expense_id": "exp-1",
                    "participant_id": "part-1",
                    "person_id": "person-alice",
                },
                {
                    "expense_id": "exp-2",
                    "participant_id": "part-2",
                    "person_id": "person-alice",
                },
                {
                    "expense_id": "exp-2",
                    "participant_id": "part-bob",
                    "person_id": "person-bob",
                },
            ],
            "Allocations": [
                {
                    "expense_id": "exp-1",
                    "participant_id": "part-1",
                    "item_id": "item-1",
                    "original_share": "10.00",
                    "final_share": "10.90",
                },
                {
                    "expense_id": "exp-2",
                    "participant_id": "part-2",
                    "item_id": "item-2",
                    "original_share": "5.00",
                    "final_share": "5.45",
                },
                {
                    "expense_id": "exp-2",
                    "participant_id": "part-bob",
                    "item_id": "item-2",
                    "original_share": "5.00",
                    "final_share": "5.45",
                },
            ],
            "Expenses": [
                {
                    "expense_id": "exp-1",
                    "expense_name": "Dinner",
                    "expense_date": "2026-11-06",
                    "calculated_total": "10.90",
                    "is_archived": "FALSE",
                },
                {
                    "expense_id": "exp-2",
                    "expense_name": "Lunch",
                    "expense_date": "2026-11-07",
                    "calculated_total": "10.90",
                    "is_archived": "FALSE",
                },
                {
                    "expense_id": "exp-3",
                    "expense_name": "Archived dinner",
                    "expense_date": "2026-11-05",
                    "calculated_total": "4.00",
                    "is_archived": "TRUE",
                },
            ],
            "Items": [
                {
                    "expense_id": "exp-1",
                    "item_id": "item-1",
                    "item_name": "Soba",
                    "sort_order": "0",
                },
                {
                    "expense_id": "exp-2",
                    "item_id": "item-2",
                    "item_name": "Tea",
                    "sort_order": "0",
                },
            ],
        }

    @patch("database.sheets_repository._assert_expense_schema")
    @patch("database.sheets_repository._sheets_service")
    @patch("database.sheets_repository._read_table")
    def test_lists_only_expenses_involving_selected_person(
        self, read_table, service, assert_schema
    ):
        service.return_value = object()
        read_table.side_effect = lambda _service, _id, tab: self.rows[tab]
        summaries = list_person_expense_summaries(
            self.spreadsheet_url, "person-alice"
        )
        self.assertEqual(
            {row["expense_id"] for row in summaries},
            {"exp-1", "exp-2"},
        )
        self.assertEqual(
            {row["expense_id"]: row["person_share"] for row in summaries},
            {"exp-1": Decimal("10.90"), "exp-2": Decimal("5.45")},
        )

    @patch("database.sheets_repository._assert_expense_schema")
    @patch("database.sheets_repository._sheets_service")
    @patch("database.sheets_repository._read_table")
    def test_archived_expenses_are_opt_in(
        self, read_table, service, assert_schema
    ):
        service.return_value = object()
        read_table.side_effect = lambda _service, _id, tab: self.rows[tab]
        active = list_person_expense_summaries(
            self.spreadsheet_url, "person-alice"
        )
        including_archived = list_person_expense_summaries(
            self.spreadsheet_url, "person-alice", include_archived=True
        )
        self.assertNotIn("exp-3", {row["expense_id"] for row in active})
        self.assertIn(
            "exp-3",
            {row["expense_id"] for row in including_archived},
        )

    @patch("database.sheets_repository._assert_expense_schema")
    @patch("database.sheets_repository._sheets_service")
    @patch("database.sheets_repository._read_table")
    def test_combines_saved_final_allocations_not_original_shares(
        self, read_table, service, assert_schema
    ):
        service.return_value = object()
        read_table.side_effect = lambda _service, _id, tab: self.rows[tab]
        result = get_combined_person_expenses(
            self.spreadsheet_url,
            "person-alice",
            "Alice",
            ["exp-1", "exp-2"],
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(
            result[0]["item_allocations"][0].per_person["Alice"],
            Decimal("10.90"),
        )
        self.assertEqual(
            result[1]["item_allocations"][0].per_person["Alice"],
            Decimal("5.45"),
        )
        self.assertEqual(
            sum((row["person_total"] for row in result), Decimal("0.00")),
            Decimal("16.35"),
        )


if __name__ == "__main__":
    unittest.main()
