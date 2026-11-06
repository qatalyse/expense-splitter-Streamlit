"""Landing page to choose a new expense or open saved expense history."""
import streamlit as st

from pages.common import clear_draft

st.title("Expense Splitter")
st.caption("Split a new bill or revisit an expense you've already saved.")

spreadsheet_url = st.session_state.get("setup_spreadsheet_url", "").strip()
if not spreadsheet_url:
    try:
        spreadsheet_url = st.secrets.get("google_sheets", {}).get("spreadsheet_url", "").strip()
    except (FileNotFoundError, KeyError, RuntimeError):
        spreadsheet_url = ""

database_ready = bool(spreadsheet_url)

st.divider()
new_col, history_col = st.columns(2)
with new_col:
    st.subheader("New expense")
    st.caption("Enter a bill, assign items and calculate each person's share.")
    if st.button("Create new expense", type="primary", use_container_width=True):
        clear_draft()
        st.session_state["setup_spreadsheet_url"] = spreadsheet_url
        st.switch_page("pages/1_Bill_Setup.py")

with history_col:
    st.subheader("Expense history")
    st.caption("Find, view, copy or edit a previously saved expense.")
    if st.button(
        "Open expense history",
        use_container_width=True,
        disabled=not database_ready,
        help=(
            "Configure and initialize Google Sheets from Bill setup first."
            if not database_ready else None
        ),
    ):
        st.session_state["history_page"] = 0
        st.session_state.pop("history_selected_expense_id", None)
        st.switch_page("pages/4_Expense_History.py")

if not database_ready:
    st.info(
        "To retrieve saved expenses, connect and initialize your Google Sheets "
        "database from Bill setup. For the URL to be remembered after a fresh "
        "session, put it in [google_sheets].spreadsheet_url in Streamlit secrets."
    )
