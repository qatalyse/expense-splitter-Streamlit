"""Search and browse saved expense summaries, loading details only on demand."""

import streamlit as st

from database.google_sheets import GoogleSheetsSetupError
from database.sheets_repository import list_expense_summaries

st.title("Expense history")
st.caption("Browse saved expenses. Item details are loaded only when you open one.")

spreadsheet_url = st.session_state.get("setup_spreadsheet_url", "").strip()
if not spreadsheet_url:
    try:
        spreadsheet_url = st.secrets.get("google_sheets", {}).get("spreadsheet_url", "").strip()
    except (FileNotFoundError, KeyError, RuntimeError):
        spreadsheet_url = ""

if not spreadsheet_url:
    st.warning("No Google Sheets URL is configured.")
    if st.button("Configure database"):
        st.switch_page("pages/1_Bill_Setup.py")
    st.stop()

search = st.text_input(
    "Search by expense name",
    key="history_search",
    placeholder="e.g. Dinner",
)
previous_search = st.session_state.get("history_previous_search")
if previous_search != search:
    st.session_state["history_page"] = 0
    st.session_state["history_previous_search"] = search

page = st.session_state.get("history_page", 0)
try:
    with st.spinner("Loading expense summaries..."):
        response = list_expense_summaries(
            spreadsheet_url,
            page=page,
            page_size=25,
            search=search,
        )
except (ValueError, GoogleSheetsSetupError) as exc:
    st.error(f"Could not retrieve expense history: {exc}")
    st.stop()

expenses = response["expenses"]
st.caption(
    f"Showing {len(expenses)} of {response['total_count']} matching expense(s). "
    "The history list loads summaries only; item breakdowns are fetched when opened."
)

if not expenses:
    st.info("No matching saved expenses were found.")
else:
    for expense in expenses:
        expense_id = expense["expense_id"]
        name = expense.get("expense_name", "").strip() or "Expense"
        expense_date = expense.get("expense_date", "")
        total = expense.get("calculated_total", "")
        revision = expense.get("revision", "1")
        with st.container(border=True):
            st.markdown(f"**{name}**")
            st.caption(f"{expense_date} · Revision {revision}")
            st.markdown(f"**SGD {Decimal(total):.2f}**" if total else "Total unavailable")
            view_col, edit_col = st.columns(2)
            if view_col.button("View breakdown", key=f"view_expense_{expense_id}", use_container_width=True):
                st.session_state["history_selected_expense_id"] = expense_id
                st.switch_page("pages/5_Expense_Detail.py")
            if edit_col.button("Edit", key=f"edit_expense_{expense_id}", use_container_width=True):
                st.session_state["history_selected_expense_id"] = expense_id
                st.session_state["history_open_for_edit"] = True
                st.switch_page("pages/5_Expense_Detail.py")

if page > 0:
    if st.button("← Newer expenses"):
        st.session_state["history_page"] = max(0, page - 1)
        st.rerun()
if response["has_more"]:
    if st.button("Load 25 older expenses", type="primary", use_container_width=True):
        st.session_state["history_page"] = page + 1
        st.rerun()

if st.button("← Home"):
    st.switch_page("pages/0_Home.py")

from decimal import Decimal
