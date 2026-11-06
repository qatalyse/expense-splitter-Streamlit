import unittest

from database.google_sheets import (
    LEGACY_PARTICIPANTS_HEADERS,
    SHEET_SCHEMA,
    extract_spreadsheet_id,
)


class SpreadsheetUrlTests(unittest.TestCase):
    def test_extracts_id_from_standard_url(self):
        url = "https://docs.google.com/spreadsheets/d/abc_DEF-123/edit#gid=0"
        self.assertEqual(extract_spreadsheet_id(url), "abc_DEF-123")

    def test_accepts_url_without_edit_suffix(self):
        url = "https://docs.google.com/spreadsheets/d/abc123"
        self.assertEqual(extract_spreadsheet_id(url), "abc123")

    def test_rejects_non_spreadsheet_url(self):
        with self.assertRaises(ValueError):
            extract_spreadsheet_id("https://drive.google.com/file/d/abc123")


class DatabaseSchemaTests(unittest.TestCase):
    def test_schema_has_five_independent_tabs_with_unique_headers(self):
        self.assertEqual(
            list(SHEET_SCHEMA),
            ["People", "Expenses", "Participants", "Items", "Allocations"],
        )
        for headers in SHEET_SCHEMA.values():
            self.assertTrue(headers)
            self.assertEqual(len(headers), len(set(headers)))

    def test_people_is_a_master_directory(self):
        self.assertEqual(
            SHEET_SCHEMA["People"],
            ("person_id", "display_name", "created_at", "updated_at"),
        )
        self.assertNotIn("expense_id", SHEET_SCHEMA["People"])

    def test_participants_links_person_to_expense(self):
        headers = SHEET_SCHEMA["Participants"]
        self.assertIn("participant_id", headers)
        self.assertIn("expense_id", headers)
        self.assertIn("person_id", headers)
        self.assertIn("name_snapshot", headers)

    def test_allocations_reference_expense_participant_and_item(self):
        headers = SHEET_SCHEMA["Allocations"]
        self.assertIn("expense_id", headers)
        self.assertIn("participant_id", headers)
        self.assertIn("item_id", headers)

    def test_legacy_participants_schema_is_recognised(self):
        self.assertEqual(
            LEGACY_PARTICIPANTS_HEADERS,
            ("participant_id", "expense_id", "name", "sort_order"),
        )
        self.assertNotEqual(
            LEGACY_PARTICIPANTS_HEADERS,
            SHEET_SCHEMA["Participants"],
        )


if __name__ == "__main__":
    unittest.main()
