import unittest
from datetime import date
from decimal import Decimal

from expense_splitter import Bill, Item, split_expense
from presentation.share_format import format_all_message, format_person_message


class ShareFormatTests(unittest.TestCase):
    def setUp(self):
        self.result = split_expense(Bill(items=[
            Item("Soba", Decimal("12.00"), ["Alice"]),
            Item("Edamame", Decimal("8.00"), ["Alice", "Bob"]),
        ]))
        self.expense_date = date(2026, 11, 6)

    def test_person_message_has_expense_date_and_monospace_fence(self):
        message = format_person_message(
            "Dinner at Restaurant", self.expense_date, "Alice",
            self.result.item_allocations, self.result.per_person["Alice"],
        )
        fence = chr(96) * 3
        self.assertTrue(message.startswith("Dinner at Restaurant 06/11/2026\n\n" + fence))
        self.assertIn("Soba", message)
        self.assertIn("Edamame", message)
        self.assertIn("TOTAL", message)
        self.assertTrue(message.endswith(fence))

    def test_long_item_name_aligns_amount_column(self):
        result = split_expense(Bill(items=[
            Item("very-long-food-item-name", Decimal("2.00"), ["Alice"]),
            Item("Tea", Decimal("1.00"), ["Alice"]),
        ]))
        message = format_person_message(
            "Lunch", self.expense_date, "Alice",
            result.item_allocations, result.per_person["Alice"],
        )
        item_lines = [
            line for line in message.splitlines()
            if "$" in line and "TOTAL" not in line
        ]
        self.assertEqual(len({line.index("$") for line in item_lines}), 1)

    def test_all_message_includes_people_and_grand_total(self):
        message = format_all_message(
            "Dinner", self.expense_date, self.result.per_person,
            self.result.item_allocations, self.result.calculated_total,
        )
        self.assertIn("Alice", message)
        self.assertIn("Bob", message)
        self.assertIn("GRAND TOTAL", message)
        self.assertTrue(message.endswith(chr(96) * 3))


if __name__ == "__main__":
    unittest.main()
