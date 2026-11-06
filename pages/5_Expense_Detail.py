"""View one saved expense or load it into the existing edit workflow."""
from datetime import date
from decimal import Decimal

import streamlit as st

from database.google_sheets import GoogleSheetsSetupError
from database.sheets_repository import (
    draft_from_expense_details,
    duplicate_draft_from_expense_details,
    get_expense_details,
    historical_result_from_details,
    set_expense_archived,
)
from presentation.expense_breakdown import render_expense_breakdown
from pages.common import clear_draft
from ui.status import create_status_slot, flash_status, render_status

st.title("Saved expense")
status = create_status_slot("detail_status")

spreadsheet_url = st.session_state.get("setup_spreadsheet_url", "").strip()
if not spreadsheet_url:
    try:
        spreadsheet_url = st.secrets.get("google_sheets", {}).get("spreadsheet_url", "").strip()
    except (FileNotFoundError, KeyError, RuntimeError):
        spreadsheet_url = ""

expense_id = st.session_state.get("history_selected_expense_id")
if not spreadsheet_url or not expense_id:
    render_status(status, "warning", "Select an expense from Expense History first.")
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
    render_status(status, "error", f"Could not load this expense: {exc}")
    st.stop()

expense = details["expense"]
name = expense.get("expense_name", "").strip() or "Expense"
expense_date = date.fromisoformat(expense["expense_date"])
result = historical_result_from_details(details)

is_archived = str(expense.get("is_archived", "FALSE")).casefold() in {"true", "1", "yes"}
st.caption(
    f"{expense_date:%d/%m/%Y} · Revision {expense.get('revision') or '1'} · "
    f"Reference {expense_id}" + (" · Archived" if is_archived else "")
)
render_expense_breakdown(name, expense_date, result)

st.subheader("Receipt reconciliation")
if result.receipt_total is None:
    render_status(status, "info", "No receipt total was recorded.")
else:
    receipt_col, difference_col = st.columns(2)
    receipt_col.metric("Receipt total", f"SGD {result.receipt_total:.2f}")
    difference_col.metric(
        "Difference",
        f"SGD {result.difference:+.2f}" if result.difference is not None else "—",
    )
    if result.reconciled:
        render_status(status, "success", "The saved receipt reconciliation passed.")
    elif result.reconciled is False:
        render_status(status, "warning", "The saved receipt and calculated total did not match.")

view_col, edit_col, duplicate_col = st.columns(3)
if view_col.button("← Expense history", use_container_width=True):
    st.session_state["history_open_for_edit"] = False
    st.switch_page("pages/4_Expense_History.py")

edit_clicked = False
if not is_archived:
    edit_clicked = edit_col.button(
        "Edit this expense",
        type="primary",
        use_container_width=True,
    )
else:
    if edit_col.button("Restore", use_container_width=True):
        try:
            set_expense_archived(
                spreadsheet_url,
                expense_id,
                archived=False,
                expected_revision=int(expense.get("revision") or "1"),
            )
            st.session_state.pop("history_detail_cache", None)
            flash_status("detail_status", "success", "Expense restored.")
            st.rerun()
        except (ValueError, GoogleSheetsSetupError) as exc:
            render_status(status, "error", str(exc))

duplicate_clicked = duplicate_col.button(
    "Duplicate",
    use_container_width=True,
)

if not is_archived:
    if st.button("Archive expense", use_container_width=True):
        st.session_state["confirm_archive_expense"] = expense_id

    if st.session_state.get("confirm_archive_expense") == expense_id:
        render_status(
            status,
            "warning",
            "Archive this expense? It will disappear from the default history list but can be restored later.",
        )
        confirm_col, cancel_col = st.columns(2)
        if confirm_col.button("Yes, archive expense", type="primary", use_container_width=True):
            try:
                set_expense_archived(
                    spreadsheet_url,
                    expense_id,
                    archived=True,
                    expected_revision=int(expense.get("revision") or "1"),
                )
                st.session_state.pop("history_detail_cache", None)
                st.session_state.pop("confirm_archive_expense", None)
                flash_status("detail_status", "success", "Expense archived. You can find it by enabling Show archived expenses.")
                st.switch_page("pages/4_Expense_History.py")
            except (ValueError, GoogleSheetsSetupError) as exc:
                render_status(status, "error", str(exc))
        if cancel_col.button("Cancel", use_container_width=True):
            st.session_state.pop("confirm_archive_expense", None)
            st.rerun()

edit_from_history = st.session_state.pop("history_open_for_edit", False)
duplicate_from_history = st.session_state.pop("history_duplicate_requested", False)

if edit_clicked or edit_from_history:
    draft = draft_from_expense_details(details, spreadsheet_url)
    st.session_state["expense_draft"] = draft
    st.session_state.pop("calculated_result", None)
    st.session_state.pop("expense_save_bundle", None)
    st.session_state.pop("expense_saved_id", None)
    st.session_state.pop("expense_saved", None)

    for key in list(st.session_state.keys()):
        if key.startswith("setup_") and key != "setup_spreadsheet_url":
            st.session_state.pop(key, None)
        if key.startswith(("item_name_", "item_price_", "item_participants_")):
            st.session_state.pop(key, None)
    st.session_state["setup_spreadsheet_url"] = spreadsheet_url
    st.session_state["setup_selected_person_ids"] = list(draft["participant_ids"])
    st.switch_page("pages/1_Bill_Setup.py")

if duplicate_clicked or duplicate_from_history:
    draft = duplicate_draft_from_expense_details(details, spreadsheet_url)
    clear_draft()
    st.session_state["expense_draft"] = draft
    st.session_state["setup_spreadsheet_url"] = spreadsheet_url
    st.session_state["setup_selected_person_ids"] = list(draft["participant_ids"])
    st.session_state.pop("editing_expense_id", None)
    st.session_state.pop("calculated_result", None)
    st.session_state.pop("expense_save_bundle", None)
    st.session_state.pop("expense_saved_id", None)
    st.switch_page("pages/1_Bill_Setup.py")

if st.button("Home", use_container_width=True):
    st.switch_page("pages/0_Home.py")
