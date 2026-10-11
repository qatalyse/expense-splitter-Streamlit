import unittest
from decimal import Decimal
from expense_splitter import Bill, BillingRules, Item, split_expense

class SplitExpenseTests(unittest.TestCase):
    def test_receipt_example(self):
        bill = Bill(items=[
            Item("Soba", Decimal("12.00"), ["Alice"]),
            Item("Ramen", Decimal("15.00"), ["Bob"]),
            Item("Edamame", Decimal("8.00"), ["Alice", "Bob"]),
        ], receipt_total=Decimal("41.97"))
        result = split_expense(bill)
        self.assertEqual(result.subtotal, Decimal("35.00"))
        self.assertEqual(result.service_charge, Decimal("3.50"))
        self.assertEqual(result.gst, Decimal("3.47"))
        self.assertEqual(result.calculated_total, Decimal("41.97"))
        self.assertEqual(result.difference, Decimal("0.00"))
        self.assertTrue(result.reconciled)
        self.assertEqual(result.per_person["Alice"], Decimal("19.19"))
        self.assertEqual(result.per_person["Bob"], Decimal("22.78"))
        self.assertEqual(sum(result.per_person.values()), result.calculated_total)

    def test_nett_skips_charges(self):
        bill = Bill([Item("Meal", Decimal("10.00"), ["Alice"])], BillingRules(prices_are_nett=True))
        result = split_expense(bill)
        self.assertEqual(result.calculated_total, Decimal("10.00"))
        self.assertEqual(result.gst, Decimal("0.00"))
        self.assertEqual(result.service_charge, Decimal("0.00"))

    def test_checksum_is_optional(self):
        result = split_expense(Bill([Item("Meal", Decimal("10.00"), ["Alice"])]))
        self.assertIsNone(result.difference)
        self.assertIsNone(result.reconciled)

    def test_unassigned_item_rejected(self):
        with self.assertRaises(ValueError):
            split_expense(Bill([Item("Meal", Decimal("10.00"), [])]))

if __name__ == "__main__":
    unittest.main()
