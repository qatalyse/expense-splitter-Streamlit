"""Page 3: itemised matrix, copyable participant messages and reconciliation."""
import streamlit as st

from database.google_sheets import GoogleSheetsSetupError
from database.sheets_repository import (
    build_expense_bundle,
    build_update_bundle,
    get_expense_details,
    save_expense_bundle,
    update_expense_bundle,
)
from pages.common import clear_draft, ensure_draft, singapore_today
from presentation.expense_breakdown import render_expense_breakdown

draft = ensure_draft()
result = st.session_state.get("calculated_result")

st.title("Expense breakdown")
st.caption("Review each person's share by item. Item amounts already include applicable charges.")
st.progress(1.0, text="Page 3 of 3 · Results")

if result is None:
    st.info("No calculation is available yet. Enter your items and calculate first.")
    if st.button("Go to item entry", type="primary"):
        st.switch_page("pages/2_Item_Entry.py")
    st.stop()

expense_name = draft.get("expense_name", "").strip() or "Expense"
expense_date = draft.get("expense_date") or singapore_today()

render_expense_breakdown(expense_name, expense_date, result)

st.subheader("Receipt reconciliation")
if result.receipt_total is None:
    st.info("No receipt total was supplied. Reconciliation was skipped.")
else:
    receipt_col, difference_col = st.columns(2)
    receipt_col.metric("Receipt total", f"SGD {result.receipt_total:.2f}")
    difference_col.metric(
        "Difference",
        f"SGD {result.difference:+.2f}",
        help="Receipt total minus calculated total.",
    )
    if result.reconciled:
        st.success("Receipt matches within SGD 0.01.")
    else:
        st.warning(
            "The receipt and calculated totals differ by more than SGD 0.01. "
            "Check the entered items, discounts and POS rounding."
        )

st.divider()
st.subheader("What next?")
spreadsheet_url = draft.get("spreadsheet_url", "").strip()
database_ready = (
    bool(spreadsheet_url)
    and st.session_state.get("sheets_database_ready_url") == spreadsheet_url
)
saved_expense_id = st.session_state.get("expense_saved_id")
editing_expense_id = draft.get("editing_expense_id")

if saved_expense_id:
    message = "Expense updated successfully" if editing_expense_id else "Expense saved successfully"
    st.success(f"{message}. Reference: {saved_expense_id}")
elif not database_ready:
    st.info("Connect and initialize Google Sheets on Page 1 before saving this expense.")
else:
    button_label = "Update existing expense" if editing_expense_id else "Save expense to Google Sheets"
    if st.button(button_label, type="primary", use_container_width=True):
        try:
            if "expense_save_bundle" not in st.session_state:
                if editing_expense_id:
                    st.session_state["expense_save_bundle"] = build_update_bundle(
                        draft,
                        result,
                        draft["editing_original_details"],
                    )
                else:
                    st.session_state["expense_save_bundle"] = build_expense_bundle(draft, result)

            with st.spinner("Updating expense..." if editing_expense_id else "Saving expense..."):
                if editing_expense_id:
                    save_summary = update_expense_bundle(
                        spreadsheet_url,
                        st.session_state["expense_save_bundle"],
                        expected_revision=int(draft.get("editing_revision", 1)),
                    )
                else:
                    save_summary = save_expense_bundle(
                        spreadsheet_url,
                        st.session_state["expense_save_bundle"],
                    )

            st.session_state["expense_saved_id"] = save_summary["expense_id"]
            st.session_state.pop("expense_save_bundle", None)
            st.session_state.pop("history_detail_cache", None)
            if editing_expense_id:
                refreshed_details = get_expense_details(spreadsheet_url, editing_expense_id)
                draft["editing_original_details"] = refreshed_details
                draft["editing_revision"] = int(refreshed_details["expense"].get("revision") or "1")
            st.success(
                ("Expense updated" if editing_expense_id else "Expense saved")
                + f" successfully. Reference: {save_summary['expense_id']}"
            )
            st.rerun()
        except (ValueError, GoogleSheetsSetupError, ArithmeticError) as exc:
            st.error(
                "The operation did not complete. Retry using the same screen; "
                f"the save bundle is retained. Details: {exc}"
            )

edit_col, reset_col = st.columns(2)
if edit_col.button("← Edit items", use_container_width=True):
    st.switch_page("pages/2_Item_Entry.py")

if reset_col.button("Start over", use_container_width=True):
    st.session_state.confirm_reset = True

if st.session_state.get("confirm_reset", False):
    st.warning("Start a new expense? Your current draft and calculation will be cleared.")
    confirm_col, cancel_col = st.columns(2)
    if confirm_col.button("Yes, start over", type="primary", use_container_width=True):
        clear_draft()
        st.switch_page("pages/1_Bill_Setup.py")
    if cancel_col.button("Keep this expense", use_container_width=True):
        st.session_state.confirm_reset = False
        st.rerun()
