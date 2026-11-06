"""Page 3: itemised matrix, copyable participant messages and reconciliation."""
import pandas as pd
import streamlit as st

from pages.common import clear_draft, ensure_draft, singapore_today
from pages.share_format import format_all_message, format_person_message

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

st.subheader("Bill total")
st.metric("Calculated total", f"SGD {result.calculated_total:.2f}")

st.subheader("Itemised allocation")
st.caption("Each cell shows that person's share of the item, including allocated GST and service charge.")
people = list(result.per_person)
table_rows = []
for allocation in result.item_allocations:
    row = {"Item": allocation.item_name}
    for person in people:
        amount = allocation.per_person.get(person)
        row[person] = f"SGD {amount:.2f}" if amount is not None else "—"
    row["Item total"] = f"SGD {allocation.total:.2f}"
    table_rows.append(row)

total_row = {"Item": "TOTAL OWED"}
for person in people:
    total_row[person] = f"SGD {result.per_person[person]:.2f}"
total_row["Item total"] = f"SGD {result.calculated_total:.2f}"
table_rows.append(total_row)

st.table(pd.DataFrame(table_rows, columns=["Item", *people, "Item total"]))

st.subheader("Copy breakdown for group chats")
st.caption(
    "Copy a participant's message or the complete breakdown. "
    "Triple backticks are included so WhatsApp can render the text in monospace."
)
for person, amount in result.per_person.items():
    with st.expander(f"{person} · SGD {amount:.2f}", expanded=False):
        message = format_person_message(
            expense_name,
            expense_date,
            person,
            result.item_allocations,
            amount,
        )
        st.code(message, language="text")

all_message = format_all_message(
    expense_name,
    expense_date,
    result.per_person,
    result.item_allocations,
    result.calculated_total,
)
st.markdown("**All participants**")
st.code(all_message, language="text")

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
st.button(
    "Save to database (coming in a later update)",
    disabled=True,
    use_container_width=True,
    help="Database persistence has not been implemented yet.",
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
