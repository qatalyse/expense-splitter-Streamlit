"""Landing page for new expenses, history and Google Sheets setup."""
import streamlit as st

from database.google_sheets import (
    GoogleSheetsSetupError,
    initialize_database,
    test_connection,
)
from pages.common import clear_draft, get_spreadsheet_url, set_spreadsheet_url
from ui.status import render_status

spreadsheet_url = get_spreadsheet_url()
if not spreadsheet_url:
    try:
        spreadsheet_url = st.secrets.get("google_sheets", {}).get(
            "spreadsheet_url", ""
        ).strip()
    except (FileNotFoundError, KeyError, RuntimeError):
        spreadsheet_url = ""
    if spreadsheet_url:
        set_spreadsheet_url(spreadsheet_url)


def _persist_home_spreadsheet_url() -> None:
    set_spreadsheet_url(st.session_state.get("home_spreadsheet_url_input", ""))


if "home_spreadsheet_url_input" not in st.session_state:
    st.session_state["home_spreadsheet_url_input"] = spreadsheet_url

left, center, right = st.columns([1, 2, 1])
with center:
    if st.button("Create new expense", type="primary", use_container_width=True):
        clear_draft()
        set_spreadsheet_url(spreadsheet_url)
        st.session_state["setup_spreadsheet_url"] = spreadsheet_url
        st.switch_page("pages/1_Bill_Setup.py")

    history_ready = (
        bool(spreadsheet_url)
        and st.session_state.get("sheets_database_ready_url") == spreadsheet_url
        and st.session_state.get("sheets_tested_url") == spreadsheet_url
    )
    if st.button(
        "Open expense history",
        use_container_width=True,
        disabled=not history_ready,
        help=(
            "Connect and initialize your Google Sheets database below first."
            if not history_ready else None
        ),
    ):
        st.session_state["history_page"] = 0
        st.session_state.pop("history_selected_expense_id", None)
        st.switch_page("pages/4_Expense_History.py")

    if st.button(
        "Consolidate expenses",
        use_container_width=True,
        disabled=not history_ready,
        help=(
            "Connect and initialize your Google Sheets database below first."
            if not history_ready else None
        ),
    ):
        st.session_state.pop("consolidation_message", None)
        st.session_state.pop("consolidation_selection", None)
        st.switch_page("pages/6_Expense_Consolidation.py")

st.divider()

spreadsheet_url = st.text_input(
    "Google Sheets URL",
    key="home_spreadsheet_url_input",
    on_change=_persist_home_spreadsheet_url,
    placeholder="https://docs.google.com/spreadsheets/d/...",
    help="The service account must have Editor access to this spreadsheet.",
)
current_url = set_spreadsheet_url(spreadsheet_url)

test_col, initialize_col = st.columns(2)
with test_col:
    test_clicked = st.button(
        "Test connection",
        use_container_width=True,
        disabled=not current_url,
        help="Checks whether the service account can access this spreadsheet. Does not change it.",
    )
with initialize_col:
    initialize_clicked = st.button(
        "Initialize database",
        type="primary",
        use_container_width=True,
        disabled=not current_url,
        help="Creates or validates the required tabs and their headers.",
    )

status = st.empty()
notice = st.session_state.pop("home_status", None)

last_connection = st.session_state.get("sheets_connection")
tested_url = st.session_state.get("sheets_tested_url")

if test_clicked:
    st.session_state.pop("sheets_connection", None)
    st.session_state.pop("sheets_tested_url", None)
    st.session_state.pop("sheets_database_ready_url", None)
    st.session_state.pop("people_directory_cache", None)
    try:
        connection = test_connection(current_url)
        st.session_state["sheets_connection"] = connection
        st.session_state["sheets_tested_url"] = current_url
        notice = {
            "level": "success",
            "message": (
                f"Connected to {connection['title']}. Existing tabs: "
                f"{', '.join(connection['sheets']) or 'none'}."
            ),
        }
    except (ValueError, GoogleSheetsSetupError) as exc:
        notice = {"level": "error", "message": str(exc)}

if initialize_clicked:
    if st.session_state.get("sheets_tested_url") != current_url:
        notice = {
            "level": "warning",
            "message": "Test this spreadsheet connection successfully before initializing it.",
        }
    else:
        try:
            setup_result = initialize_database(current_url)
            st.session_state["sheets_database_ready_url"] = current_url
            st.session_state.pop("people_directory_cache", None)
            created = setup_result["created_tabs"]
            if created:
                message = "Database initialized. Created tabs: " + ", ".join(created) + "."
            else:
                message = "Database is ready. All five tabs and headers are present."
            upgraded = setup_result.get("upgraded_legacy_tabs", [])
            if upgraded:
                message += (
                    " Upgraded existing tab headers: "
                    + ", ".join(upgraded)
                    + ". Existing records were preserved."
                )
            notice = {"level": "success", "message": message}
        except (ValueError, GoogleSheetsSetupError) as exc:
            notice = {"level": "error", "message": str(exc)}

if notice:
    render_status(status, notice["level"], notice["message"])
else:
    database_ready = (
        bool(current_url)
        and st.session_state.get("sheets_database_ready_url") == current_url
        and tested_url == current_url
    )
    if not current_url:
        render_status(
            status,
            "info",
            "Enter a Google Sheets URL. To prefill it after a fresh session, "
            "configure [google_sheets].spreadsheet_url in Streamlit secrets.",
        )
    elif tested_url and tested_url != current_url:
        render_status(
            status,
            "warning",
            "The spreadsheet URL changed. Test the new URL before initializing the database.",
        )
    elif database_ready and last_connection:
        render_status(
            status,
            "success",
            f"Connected to {last_connection['title']} · Database ready · 5 tabs verified",
        )
    elif last_connection and tested_url == current_url:
        render_status(status, "success", f"Connected to {last_connection['title']}.")
    else:
        render_status(
            status,
            "info",
            "Test the connection, then initialize the database to enable expense history.",
        )
