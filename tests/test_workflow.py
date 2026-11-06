"""Tests for the UI draft's pure helper functions."""
import unittest

from ui.state import BILLING_MODES, new_item, parse_people


class WorkflowTests(unittest.TestCase):
    def test_parse_participants(self):
        self.assertEqual(parse_people(" Alice, Bob , Charlie "), ["Alice", "Bob", "Charlie"])

    def test_reject_duplicate_names_ignoring_case(self):
        with self.assertRaises(ValueError):
            parse_people("Alice, alice")

    def test_reject_empty_participant_list(self):
        with self.assertRaises(ValueError):
            parse_people(" , ")

    def test_new_rows_have_unique_stable_ids(self):
        first, second = new_item(), new_item()
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["participants"], [])
        self.assertEqual(first["price"], "")

    def test_billing_modes_are_unambiguous(self):
        self.assertEqual(BILLING_MODES["GST + service charge"], (True, True, False))
        self.assertEqual(BILLING_MODES["Nett (no additional charges)"], (False, False, True))


if __name__ == "__main__":
    unittest.main()
