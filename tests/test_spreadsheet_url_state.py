import unittest
from unittest.mock import patch

import pages.common as common


class SpreadsheetURLStateTests(unittest.TestCase):
    def test_get_reads_persistent_session_value_first(self):
        state = {
            "app_spreadsheet_url": "https://docs.google.com/spreadsheets/d/new/edit",
            "setup_spreadsheet_url": "https://docs.google.com/spreadsheets/d/old/edit",
        }
        with patch.object(common.st, "session_state", state):
            self.assertEqual(
                common.get_spreadsheet_url(),
                "https://docs.google.com/spreadsheets/d/new/edit",
            )

    def test_get_migrates_legacy_session_value(self):
        state = {
            "setup_spreadsheet_url": " https://docs.google.com/spreadsheets/d/legacy/edit "
        }
        with patch.object(common.st, "session_state", state):
            self.assertEqual(
                common.get_spreadsheet_url(),
                "https://docs.google.com/spreadsheets/d/legacy/edit",
            )
            self.assertEqual(
                state["app_spreadsheet_url"],
                "https://docs.google.com/spreadsheets/d/legacy/edit",
            )

    def test_set_persists_url_and_invalidates_connection_for_changed_url(self):
        state = {
            "app_spreadsheet_url": "https://docs.google.com/spreadsheets/d/old/edit",
            "sheets_connection": {"title": "Old sheet"},
            "sheets_tested_url": "https://docs.google.com/spreadsheets/d/old/edit",
            "sheets_database_ready_url": "https://docs.google.com/spreadsheets/d/old/edit",
            "people_directory_cache": {"spreadsheet_url": "old"},
            "consolidation_people::old": [],
            "consolidation_summaries::old::person-1::False": [],
            "consolidation_message": {"message": "stale"},
        }
        with patch.object(common.st, "session_state", state):
            value = common.set_spreadsheet_url(
                " https://docs.google.com/spreadsheets/d/new/edit "
            )
            self.assertEqual(value, "https://docs.google.com/spreadsheets/d/new/edit")
            self.assertEqual(state["app_spreadsheet_url"], value)
            self.assertNotIn("sheets_connection", state)
            self.assertNotIn("sheets_tested_url", state)
            self.assertNotIn("sheets_database_ready_url", state)
            self.assertNotIn("people_directory_cache", state)
            self.assertNotIn("consolidation_people::old", state)
            self.assertNotIn("consolidation_summaries::old::person-1::False", state)
            self.assertNotIn("consolidation_message", state)

    def test_set_same_url_keeps_validated_connection(self):
        url = "https://docs.google.com/spreadsheets/d/sheet/edit"
        state = {
            "app_spreadsheet_url": url,
            "sheets_tested_url": url,
            "sheets_database_ready_url": url,
        }
        with patch.object(common.st, "session_state", state):
            common.set_spreadsheet_url(url)
        self.assertEqual(state["sheets_tested_url"], url)
        self.assertEqual(state["sheets_database_ready_url"], url)


if __name__ == "__main__":
    unittest.main()
