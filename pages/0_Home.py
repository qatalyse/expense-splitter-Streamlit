"""Landing page for new expenses, history and Google Sheets setup."""
import streamlit as st

from database.google_sheets import (
    GoogleSheetsSetupError,
    initialize_database,
    test_connection,
)
from pages.common import clear_draft

st.title("Expense Splitter")

spreadsheet_url = st.session_state.get("setup_spreadsheet_url", "").strip()
if not spreadsheet_url:
    try:
        spreadsheet_url = st.secrets.get("google_sheets", {}).get(
            "spreadsheet_url", ""
        ).strip()
    except (FileNotFoundError, KeyError, RuntimeError):
        spreadsheet_url = ""

# Keep both primary actions simple and vertically stacked.
if st.button("Create new expense", type="primary", use_container_width=True):
    clear_draft()
    st.session_state["setup_spreadsheet_url"] = spreadsheet_url
    st.switch_page("pages/1_Bill_Setup.py")

database_ready = (
    bool(spreadsheet_url)
    and st.session_state.get("sheets_database_ready_url") == spreadsheet_url
    and st.session_state.get("sheets_tested_url") == spreadsheet_url
)

if st.button(
    "Open expense history",
    use_container_width=True,
    disabled=not database_ready,
    help=(
        "Connect and initialize your Google Sheets database below first."
        if not database_ready else None
    ),
):
    st.session_state["history_page"] = 0
    st.session_state.pop("history_selected_expense_id", None)
    st.switch_page("pages/4_Expense_History.py")

st.divider()

# Database setup lives on Home so connection management is available before
# entering either workflow. The title is intentionally omitted to keep Home light.
st.caption(
    "Connect your Google Sheet to save new expenses and retrieve your expense history. "
    "The service account needs Editor access to the spreadsheet."
)
spreadsheet_url = st.text_input(
    "Google Sheets URL",
    key="setup_spreadsheet_url",
    value=spreadsheet_url,
    placeholder="https://docs.google.com/spreadsheets/d/...",
    help="The service account must have Editor access to this spreadsheet.",
)
current_url = spreadsheet_url.strip()

last_connection = st.session_state.get("sheets_connection")
tested_url = st.session_state.get("sheets_tested_url")

if current_url and tested_url == current_url and last_connection:
    st.success(f"Connected to **{last_connection['title']}**.")
elif tested_url and tested_url != current_url:
    st.info(
        "The spreadsheet URL changed. Test the new URL before initializing "
        "the database or using the People directory."
    )

if not current_url:
    st.info(
        "Enter your Google Sheets URL, then test the connection and initialize "
        "the database. To prefill the URL after a fresh session, configure "
        "[google_sheets].spreadsheet_url in Streamlit secrets."
    )

if current_url and st.session_state.get("sheets_database_ready_url") == current_url:
    st.success("Google Sheets database is ready.")

initialization_notice = st.session_state.pop("sheets_initialization_notice", None)
if initialization_notice:
    st.success(initialization_notice)

if st.button(
    "Test connection",
    use_container_width=True,
    disabled=not current_url,
    help="Checks whether the service account can access this spreadsheet. Does not change it.",
):
    st.session_state.pop("sheets_connection", None)
    st.session_state.pop("sheets_tested_url", None)
    st.session_state.pop("sheets_database_ready_url", None)
    st.session_state.pop("people_directory_cache", None)
    try:
        connection = test_connection(current_url)
        st.session_state["sheets_connection"] = connection
        st.session_state["sheets_tested_url"] = current_url
        st.success(
            f"Connection successful: **{connection['title']}**. "
            f"Existing tabs: {', '.join(connection['sheets']) or 'none'}."
        )
    except (ValueError, GoogleSheetsSetupError) as exc:
        st.error(str(exc))

if st.button(
    "Initialize database",
    type="primary",
    use_container_width=True,
    disabled=not current_url,
    help="Creates or validates the five required tabs and their headers.",
):
    if st.session_state.get("sheets_tested_url") != current_url:
        st.warning(
            "Test this spreadsheet connection successfully before initializing it."
        )
    else:
        try:
            setup_result = initialize_database(current_url)
            st.session_state["sheets_database_ready_url"] = current_url
            st.session_state.pop("people_directory_cache", None)
            created = setup_result["created_tabs"]
            if created:
                notice = "Database initialized. Created tabs: " + ", ".join(created) + "."
            else:
                notice = "Database is ready. All five tabs and headers are present."
            upgraded = setup_result.get("upgraded_legacy_tabs", [])
            if upgraded:
                notice += (
                    " Upgraded existing tab headers: "
                    + ", ".join(upgraded)
                    + ". Existing records were preserved."
                )
            st.session_state["sheets_initialization_notice"] = notice
            st.rerun()
        except (ValueError, GoogleSheetsSetupError) as exc:
            st.error(str(exc))

if not database_ready:
    st.caption(
        "Expense history becomes available after a successful connection test "
        "and database initialization."
    )
