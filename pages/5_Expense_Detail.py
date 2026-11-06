"""View one saved expense or load it into the existing edit workflow."""
from datetime import date
from decimal import Decimal

import streamlit as st

from database.google_sheets import GoogleSheetsSetupError
from database.sheets_repository import (
    draft_from_expense_details,
    get_expense_details,
    historical_result_from_details,
)
from presentation.expense_breakdown import render_expense_breakdown

st.title("Saved expense")

spreadsheet_url = st.session_state.get("setup_spreadsheet_url", "").strip()
if not spreadsheet_url:
    try:
        spreadsheet_url = st.secrets.get("google_sheets", {}).get("spreadsheet_url", "").strip()
    except (FileNotFoundError, KeyError, RuntimeError):
        spreadsheet_url = ""

expense_id = st.session_state.get("history_selected_expense_id")
if not spreadsheet_url or not expense_id:
    st.warning("Select an expense from Expense History first.")
    if st.button("Back to history"):
        st.switch_page("pages/4_Expense_History.py")
    st.stop()

cache = st.session_state.get("history_detail_cache", {})
try:
    if cache.get("expense_id") != expense_id or cache.get("spreadsheet_url") != spreadsheet_url:
        with st.spinner("Loading saved expense details..."):
            details = get_expense_details(spreadsheet_url, expense_id)
        st.session_state["history_detail_cache"] = {
            "expense_id": expense_id,
            "spreadsheet_url": spreadsheet_url,
            "details": details,
        }
    else:
        details = cache["details"]
except (ValueError, GoogleSheetsSetupError) as exc:
    st.error(f"Could not load this expense: {exc}")
    st.stop()

expense = details["expense"]
name = expense.get("expense_name", "").strip() or "Expense"
expense_date = date.fromisoformat(expense["expense_date"])
result = historical_result_from_details(details)

st.caption(
    f"{expense_date:%d/%m/%Y} · Revision {expense.get('revision') or '1'} · "
    f"Reference {expense_id}"
)
render_expense_breakdown(name, expense_date, result)

st.subheader("Receipt reconciliation")
if result.receipt_total is None:
    st.info("No receipt total was recorded.")
else:
    receipt_col, difference_col = st.columns(2)
    receipt_col.metric("Receipt total", f"SGD {result.receipt_total:.2f}")
    difference_col.metric(
        "Difference",
        f"SGD {result.difference:+.2f}" if result.difference is not None else "—",
    )
    if result.reconciled:
        st.success("The saved receipt reconciliation passed.")
    elif result.reconciled is False:
        st.warning("The saved receipt and calculated total did not match.")

view_col, edit_col = st.columns(2)
if view_col.button("← Expense history", use_container_width=True):
    st.session_state["history_open_for_edit"] = False
    st.switch_page("pages/4_Expense_History.py")

edit_clicked = edit_col.button("Edit this expense", type="primary", use_container_width=True)
edit_from_history = st.session_state.pop("history_open_for_edit", False)

if edit_clicked or edit_from_history:
    draft = draft_from_expense_details(details, spreadsheet_url)
    st.session_state["expense_draft"] = draft
    st.session_state.pop("calculated_result", None)
    st.session_state.pop("expense_save_bundle", None)
    st.session_state.pop("expense_saved_id", None)
    st.session_state.pop("expense_saved", None)

    # Clear stale widget values from a previous new/edit workflow. Page 1 will
    # initialise its widgets from the loaded expense draft.
    for key in list(st.session_state.keys()):
        if key.startswith("setup_") and key != "setup_spreadsheet_url":
            st.session_state.pop(key, None)
        if key.startswith(("item_name_", "item_price_", "item_participants_")):
            st.session_state.pop(key, None)
    st.session_state["setup_spreadsheet_url"] = spreadsheet_url
    st.session_state["setup_selected_person_ids"] = list(draft["participant_ids"])
    st.session_state["editing_expense_id"] = expense_id
    st.switch_page("pages/1_Bill_Setup.py")

if st.button("Home", use_container_width=True):
    st.switch_page("pages/0_Home.py")
