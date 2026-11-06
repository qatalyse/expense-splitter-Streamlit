"""Google Sheets connection checks and initial database schema setup."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DEFAULT_CREDENTIALS_FILE = "expense-splitter-service.json"

# One spreadsheet holds all expenses. Each tab represents a logical table.
SHEET_SCHEMA: dict[str, tuple[str, ...]] = {
    "Expenses": (
        "expense_id",
        "expense_name",
        "expense_date",
        "currency",
        "receipt_total",
        "subtotal",
        "gst_enabled",
        "gst_rate",
        "gst_amount",
        "service_charge_enabled",
        "service_charge_rate",
        "service_charge_amount",
        "prices_are_nett",
        "calculated_total",
        "difference",
        "reconciled",
        "created_at",
        "calculation_version",
    ),
    "Participants": (
        "participant_id",
        "expense_id",
        "name",
        "sort_order",
    ),
    "Items": (
        "item_id",
        "expense_id",
        "item_name",
        "original_price",
        "sort_order",
    ),
    "Allocations": (
        "allocation_id",
        "expense_id",
        "item_id",
        "participant_id",
        "original_share",
        "final_share",
    ),
}

_SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


class GoogleSheetsSetupError(RuntimeError):
    """Raised when credentials, permissions or sheet structure are invalid."""


def extract_spreadsheet_id(spreadsheet_url: str) -> str:
    """Extract and validate the ID from a standard Google Sheets URL."""
    match = _SPREADSHEET_ID_RE.search(spreadsheet_url.strip())
    if not match:
        raise ValueError(
            "Enter a valid Google Sheets URL, such as "
            "https://docs.google.com/spreadsheets/d/.../edit."
        )
    return match.group(1)


def _read_secret_config() -> tuple[dict[str, Any] | None, str | None]:
    """Read optional Streamlit secrets without requiring secrets.toml locally."""
    try:
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"]), None
        if "google_sheets" in st.secrets:
            config = st.secrets["google_sheets"]
            credentials_file = config.get("credentials_file")
            if credentials_file:
                return None, str(credentials_file)
    except (FileNotFoundError, KeyError, RuntimeError):
        # Local JSON fallback is useful during development.
        pass
    return None, None


def get_credentials():
    """Load credentials from deployed Streamlit secrets or a local JSON key."""
    service_account_info, configured_path = _read_secret_config()
    try:
        if service_account_info:
            return service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=[SHEETS_SCOPE],
            )

        credentials_path = Path(
            configured_path or DEFAULT_CREDENTIALS_FILE
        ).expanduser()
        if not credentials_path.is_file():
            raise GoogleSheetsSetupError(
                "Service-account credentials were not found. For local development, "
                f"place {DEFAULT_CREDENTIALS_FILE!r} in the repository root. "
                "For Streamlit Community Cloud, add the [gcp_service_account] "
                "credentials to the app's Secrets settings."
            )

        return service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=[SHEETS_SCOPE],
        )
    except (ValueError, OSError, KeyError) as exc:
        raise GoogleSheetsSetupError(
            f"Could not load service-account credentials: {exc}"
        ) from exc


def _sheets_service():
    """Build an authenticated Sheets API client."""
    credentials = get_credentials()
    try:
        return build(
            "sheets",
            "v4",
            credentials=credentials,
            cache_discovery=False,
        )
    except Exception as exc:
        raise GoogleSheetsSetupError(
            f"Could not initialise the Google Sheets API client: {exc}"
        ) from exc


def _translate_api_error(exc: Exception) -> GoogleSheetsSetupError:
    """Return an actionable, non-secret-leaking API error message."""
    if isinstance(exc, HttpError):
        status = getattr(exc.resp, "status", None)
        if status == 403:
            return GoogleSheetsSetupError(
                "Google denied access. Check that Google Sheets API is enabled "
                "and that the spreadsheet has been shared with the service-account "
                "email as Editor."
            )
        if status == 404:
            return GoogleSheetsSetupError(
                "Spreadsheet not found. Check the URL and confirm that the "
                "service account has access to it."
            )
        return GoogleSheetsSetupError(
            f"Google Sheets returned HTTP {status}. Check the URL, API enablement "
            "and service-account permissions."
        )
    return GoogleSheetsSetupError(
        f"Google Sheets connection failed: {exc}"
    )


def test_connection(spreadsheet_url: str) -> dict[str, Any]:
    """Verify authentication and read access without modifying the spreadsheet."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    try:
        service = _sheets_service()
        metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="spreadsheetId,properties(title),sheets(properties(title))",
        ).execute()
    except GoogleSheetsSetupError:
        raise
    except Exception as exc:
        raise _translate_api_error(exc) from exc

    titles = [
        sheet["properties"]["title"]
        for sheet in metadata.get("sheets", [])
    ]
    return {
        "spreadsheet_id": spreadsheet_id,
        "title": metadata.get("properties", {}).get("title", "Untitled"),
        "sheets": titles,
    }


def initialize_database(spreadsheet_url: str) -> dict[str, Any]:
    """Create missing tabs and initialize headers without overwriting user data.

    Existing tabs must either be empty or have exactly the expected header row.
    Any mismatch stops initialization before changes are made.
    """
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    service = _sheets_service()

    try:
        metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="spreadsheetId,properties(title),sheets(properties(sheetId,title))",
        ).execute()

        existing = {
            sheet["properties"]["title"]: sheet["properties"]["sheetId"]
            for sheet in metadata.get("sheets", [])
        }

        # Preflight every existing tab before creating or writing anything.
        headers_to_write: dict[str, list[str]] = {}
        for title, expected_headers in SHEET_SCHEMA.items():
            if title not in existing:
                headers_to_write[title] = list(expected_headers)
                continue

            response = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"'{title}'!1:1",
            ).execute()
            actual_rows = response.get("values", [])
            actual_headers = actual_rows[0] if actual_rows else []

            if not actual_headers:
                headers_to_write[title] = list(expected_headers)
            elif actual_headers != list(expected_headers):
                raise GoogleSheetsSetupError(
                    f"The {title!r} tab already has different column headers. "
                    "No changes were made. Rename or back up the existing tab "
                    "before initializing this schema."
                )

        missing_titles = [
            title for title in SHEET_SCHEMA if title not in existing
        ]
        if missing_titles:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "requests": [
                        {"addSheet": {"properties": {"title": title}}}
                        for title in missing_titles
                    ]
                },
            ).execute()

        # Write all headers (including matching headers on existing tabs) as
        # a single values batch, both initializing blank tabs and verifying write access.
        data = [
            {
                "range": f"'{title}'!A1",
                "majorDimension": "ROWS",
                "values": [list(SHEET_SCHEMA[title])],
            }
            for title in SHEET_SCHEMA
        ]
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": data},
        ).execute()

        final_metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="properties(title),sheets(properties(title))",
        ).execute()
    except GoogleSheetsSetupError:
        raise
    except Exception as exc:
        raise _translate_api_error(exc) from exc

    return {
        "title": final_metadata.get("properties", {}).get("title", "Untitled"),
        "tabs": list(SHEET_SCHEMA),
        "created_tabs": missing_titles,
        "headers_initialized": list(headers_to_write),
    }
