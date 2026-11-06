import unittest
from decimal import Decimal

from expense_splitter import Bill, BillingRules, Item, split_expense


class SplitExpenseTests(unittest.TestCase):
    def setUp(self):
        self.bill = Bill(items=[
            Item("Soba", Decimal("12.00"), ["Alice"]),
            Item("Ramen", Decimal("15.00"), ["Bob"]),
            Item("Edamame", Decimal("8.00"), ["Alice", "Bob"]),
        ], receipt_total=Decimal("41.97"))

    def test_receipt_example(self):
        result = split_expense(self.bill)
        self.assertEqual(result.subtotal, Decimal("35.00"))
        self.assertEqual(result.service_charge, Decimal("3.50"))
        self.assertEqual(result.gst, Decimal("3.47"))
        self.assertEqual(result.calculated_total, Decimal("41.97"))
        self.assertEqual(result.difference, Decimal("0.00"))
        self.assertTrue(result.reconciled)
        self.assertEqual(result.per_person["Alice"], Decimal("19.19"))
        self.assertEqual(result.per_person["Bob"], Decimal("22.78"))
        self.assertEqual(sum(result.per_person.values()), result.calculated_total)

    def test_item_allocations_include_charges_and_reconcile(self):
        result = split_expense(self.bill)
        self.assertEqual([row.item_name for row in result.item_allocations],
                         ["Soba", "Ramen", "Edamame"])
        self.assertEqual(result.item_allocations[0].per_person["Alice"], Decimal("14.39"))
        self.assertEqual(result.item_allocations[1].per_person["Bob"], Decimal("17.99"))
        self.assertEqual(result.item_allocations[2].per_person["Alice"], Decimal("4.80"))
        self.assertEqual(result.item_allocations[2].per_person["Bob"], Decimal("4.79"))
        self.assertEqual(
            sum((row.total for row in result.item_allocations), Decimal("0.00")),
            result.calculated_total,
        )
        for person, person_total in result.per_person.items():
            item_sum = sum(
                (row.per_person.get(person, Decimal("0.00")) for row in result.item_allocations),
                Decimal("0.00"),
            )
            self.assertEqual(item_sum, person_total)

    def test_nett_skips_charges(self):
        bill = Bill(
            [Item("Meal", Decimal("10.00"), ["Alice"])],
            BillingRules(prices_are_nett=True),
        )
        result = split_expense(bill)
        self.assertEqual(result.calculated_total, Decimal("10.00"))
        self.assertEqual(result.gst, Decimal("0.00"))
        self.assertEqual(result.service_charge, Decimal("0.00"))
        self.assertEqual(result.item_allocations[0].per_person["Alice"], Decimal("10.00"))

    def test_checksum_is_optional(self):
        result = split_expense(Bill([Item("Meal", Decimal("10.00"), ["Alice"])]))
        self.assertIsNone(result.difference)
        self.assertIsNone(result.reconciled)

    def test_unassigned_item_rejected(self):
        with self.assertRaises(ValueError):
            split_expense(Bill([Item("Meal", Decimal("10.00"), [])]))


if __name__ == "__main__":
    unittest.main()
