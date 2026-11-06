import unittest
from datetime import date
from decimal import Decimal

from database.sheets_repository import (
    build_update_bundle,
    draft_from_expense_details,
    historical_result_from_details,
)
from expense_splitter import Bill, BillingRules, Item, split_expense


class HistoricalExpenseTests(unittest.TestCase):
    def setUp(self):
        self.draft = {
            "expense_name": "Dinner",
            "expense_date": date(2026, 11, 7),
            "billing_mode": "Nett",
            "receipt_total": "20.00",
            "participants": ["Alice", "Bob"],
            "participant_id_by_name": {
                "Alice": "person-alice",
                "Bob": "person-bob",
            },
            "items": [
                {"id": "draft-1", "item_id": "item-1", "name": "Soba",
                 "price": "12.00", "participants": ["Alice"]},
                {"id": "draft-2", "item_id": "item-2", "name": "Edamame",
                 "price": "8.00", "participants": ["Alice", "Bob"]},
            ],
        }
        self.result = split_expense(Bill(
            items=[
                Item("Soba", Decimal("12.00"), ["Alice"]),
                Item("Edamame", Decimal("8.00"), ["Alice", "Bob"]),
            ],
            billing=BillingRules(prices_are_nett=True),
            receipt_total=Decimal("20.00"),
            expense_name="Dinner",
            expense_date=date(2026, 11, 7),
        ))
        self.details = {
            "expense": {
                "expense_id": "expense-1",
                "expense_name": "Dinner",
                "expense_date": "2026-11-07",
                "currency": "SGD",
                "receipt_total": "20.00",
                "subtotal": "20.00",
                "gst_enabled": "FALSE",
                "gst_rate": "0",
                "gst_amount": "0.00",
                "service_charge_enabled": "FALSE",
                "service_charge_rate": "0",
                "service_charge_amount": "0.00",
                "prices_are_nett": "TRUE",
                "calculated_total": "20.00",
                "difference": "0.00",
                "reconciled": "TRUE",
                "created_at": "2026-11-07T01:00:00+00:00",
                "calculation_version": "1",
                "updated_at": "2026-11-07T01:00:00+00:00",
                "revision": "1",
                "_row_number": 2,
            },
            "Participants": [
                {"participant_id": "participant-1", "expense_id": "expense-1",
                 "person_id": "person-alice", "name_snapshot": "Alice", "sort_order": "0",
                 "_row_number": 2},
                {"participant_id": "participant-2", "expense_id": "expense-1",
                 "person_id": "person-bob", "name_snapshot": "Bob", "sort_order": "1",
                 "_row_number": 3},
            ],
            "Items": [
                {"item_id": "item-1", "expense_id": "expense-1", "item_name": "Soba",
                 "original_price": "12.00", "sort_order": "0", "_row_number": 2},
                {"item_id": "item-2", "expense_id": "expense-1", "item_name": "Edamame",
                 "original_price": "8.00", "sort_order": "1", "_row_number": 3},
            ],
            "Allocations": [
                {"allocation_id": "allocation-1", "expense_id": "expense-1",
                 "item_id": "item-1", "participant_id": "participant-1",
                 "original_share": "12.00", "final_share": "12.00", "_row_number": 2},
                {"allocation_id": "allocation-2", "expense_id": "expense-1",
                 "item_id": "item-2", "participant_id": "participant-1",
                 "original_share": "4.00", "final_share": "4.00", "_row_number": 3},
                {"allocation_id": "allocation-3", "expense_id": "expense-1",
                 "item_id": "item-2", "participant_id": "participant-2",
                 "original_share": "4.00", "final_share": "4.00", "_row_number": 4},
            ],
            "sheet_ids": {
                "Expenses": 1, "Participants": 2, "Items": 3,
                "Allocations": 4, "People": 5,
            },
        }

    def test_historical_result_uses_saved_final_allocations(self):
        result = historical_result_from_details(self.details)
        self.assertEqual(result.calculated_total, Decimal("20.00"))
        self.assertEqual(result.per_person["Alice"], Decimal("16.00"))
        self.assertEqual(result.per_person["Bob"], Decimal("4.00"))
        self.assertEqual(result.item_allocations[0].per_person["Alice"], Decimal("12.00"))

    def test_historical_result_preserves_receipt_reconciliation(self):
        result = historical_result_from_details(self.details)
        self.assertEqual(result.receipt_total, Decimal("20.00"))
        self.assertEqual(result.difference, Decimal("0.00"))
        self.assertTrue(result.reconciled)

    def test_saved_expense_converts_to_existing_three_page_draft(self):
        draft = draft_from_expense_details(
            self.details,
            "https://docs.google.com/spreadsheets/d/test123/edit",
        )
        self.assertEqual(draft["editing_expense_id"], "expense-1")
        self.assertEqual(draft["editing_revision"], 1)
        self.assertEqual(draft["participants"], ["Alice", "Bob"])
        self.assertEqual(draft["items"][0]["item_id"], "item-1")
        self.assertEqual(draft["items"][1]["participants"], ["Alice", "Bob"])

    def test_update_bundle_retains_expense_person_item_and_matching_allocation_ids(self):
        draft = dict(self.draft)
        draft["editing_expense_id"] = "expense-1"
        changed_result = split_expense(Bill(
            items=[
                Item("Soba", Decimal("14.00"), ["Alice"]),
                Item("Edamame", Decimal("8.00"), ["Alice", "Bob"]),
            ],
            billing=BillingRules(prices_are_nett=True),
            receipt_total=Decimal("22.00"),
            expense_name="Dinner",
            expense_date=date(2026, 11, 7),
        ))
        draft["items"] = [dict(item) for item in self.draft["items"]]
        bundle = build_update_bundle(draft, changed_result, self.details)

        self.assertEqual(bundle["expense_id"], "expense-1")
        self.assertEqual(bundle["Expenses"][0]["expense_id"], "expense-1")
        self.assertEqual(bundle["Expenses"][0]["created_at"], self.details["expense"]["created_at"])
        self.assertEqual(bundle["Expenses"][0]["revision"], "2")
        self.assertEqual(
            {row["participant_id"] for row in bundle["Participants"]},
            {"participant-1", "participant-2"},
        )
        self.assertEqual(
            {row["item_id"] for row in bundle["Items"]},
            {"item-1", "item-2"},
        )
        matching = {
            (row["item_id"], row["participant_id"]): row["allocation_id"]
            for row in bundle["Allocations"]
        }
        self.assertEqual(matching[("item-2", "participant-2")], "allocation-3")
        self.assertEqual(bundle["Expenses"][0]["calculated_total"], "22.00")


if __name__ == "__main__":
    unittest.main()
