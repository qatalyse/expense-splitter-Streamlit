import unittest

from database.google_sheets import SHEET_SCHEMA, extract_spreadsheet_id


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

    def test_schema_has_four_tabs_with_unique_headers(self):
        self.assertEqual(
            list(SHEET_SCHEMA),
            ["Expenses", "Participants", "Items", "Allocations"],
        )
        for headers in SHEET_SCHEMA.values():
            self.assertTrue(headers)
            self.assertEqual(len(headers), len(set(headers)))


if __name__ == "__main__":
    unittest.main()
