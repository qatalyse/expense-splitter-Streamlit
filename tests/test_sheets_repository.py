import unittest
from datetime import date
from decimal import Decimal

from expense_splitter import Bill, Item, split_expense
from database.sheets_repository import build_expense_bundle


class ExpenseBundleTests(unittest.TestCase):
    def setUp(self):
        self.draft = {
            "expense_name": "Dinner",
            "expense_date": date(2026, 11, 7),
            "billing_mode": "GST + service charge",
            "receipt_total": "41.97",
            "participants": ["Alice", "Bob"],
            "participant_id_by_name": {
                "Alice": "person-alice",
                "Bob": "person-bob",
            },
            "items": [
                {"name": "Soba", "price": "12.00", "participants": ["Alice"]},
                {"name": "Ramen", "price": "15.00", "participants": ["Bob"]},
                {"name": "Edamame", "price": "8.00", "participants": ["Alice", "Bob"]},
            ],
        }
        self.result = split_expense(Bill(
            items=[
                Item("Soba", Decimal("12.00"), ["Alice"]),
                Item("Ramen", Decimal("15.00"), ["Bob"]),
                Item("Edamame", Decimal("8.00"), ["Alice", "Bob"]),
            ],
            receipt_total=Decimal("41.97"),
            expense_name="Dinner",
            expense_date=date(2026, 11, 7),
        ))

    def test_bundle_contains_all_four_expense_tables(self):
        bundle = build_expense_bundle(self.draft, self.result)
        self.assertEqual(
            set(bundle),
            {"expense_id", "Expenses", "Participants", "Items", "Allocations"},
        )
        self.assertEqual(len(bundle["Expenses"]), 1)
        self.assertEqual(len(bundle["Participants"]), 2)
        self.assertEqual(len(bundle["Items"]), 3)
        self.assertEqual(len(bundle["Allocations"]), 4)

    def test_bundle_relationships_use_stable_ids(self):
        bundle = build_expense_bundle(self.draft, self.result)
        expense_id = bundle["expense_id"]
        participant_ids = {
            row["person_id"]: row["participant_id"]
            for row in bundle["Participants"]
        }
        item_ids = {row["item_name"]: row["item_id"] for row in bundle["Items"]}

        self.assertTrue(all(row["expense_id"] == expense_id for row in bundle["Participants"]))
        self.assertTrue(all(row["expense_id"] == expense_id for row in bundle["Items"]))
        self.assertTrue(all(row["expense_id"] == expense_id for row in bundle["Allocations"]))
        self.assertEqual(
            {row["participant_id"] for row in bundle["Allocations"]},
            set(participant_ids.values()),
        )
        self.assertEqual(
            {row["item_id"] for row in bundle["Allocations"]},
            set(item_ids.values()),
        )

    def test_final_allocations_reconcile_to_calculated_total(self):
        bundle = build_expense_bundle(self.draft, self.result)
        final_total = sum(
            (Decimal(row["final_share"]) for row in bundle["Allocations"]),
            Decimal("0.00"),
        )
        self.assertEqual(final_total, self.result.calculated_total)
        self.assertEqual(bundle["Expenses"][0]["calculated_total"], "41.97")

    def test_original_shares_retain_pre_charge_amounts(self):
        bundle = build_expense_bundle(self.draft, self.result)
        original_total = sum(
            (Decimal(row["original_share"]) for row in bundle["Allocations"]),
            Decimal("0.00"),
        )
        self.assertEqual(original_total, Decimal("35.00"))

    def test_bundle_has_unique_ids_and_stable_expense_id_field(self):
        bundle = build_expense_bundle(self.draft, self.result)
        self.assertTrue(bundle["expense_id"])
        for tab, id_column in (
            ("Participants", "participant_id"),
            ("Items", "item_id"),
            ("Allocations", "allocation_id"),
        ):
            ids = [row[id_column] for row in bundle[tab]]
            self.assertEqual(len(ids), len(set(ids)))

    def test_missing_people_mapping_is_rejected(self):
        draft = dict(self.draft)
        draft["participant_id_by_name"] = {"Alice": "person-alice"}
        with self.assertRaises(ValueError):
            build_expense_bundle(draft, self.result)


if __name__ == "__main__":
    unittest.main()
