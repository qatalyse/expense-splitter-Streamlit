"""Page 3: calculation results and next-step actions."""
import streamlit as st

from pages.common import clear_draft, ensure_draft

ensure_draft()
result = st.session_state.get("calculated_result")

st.title("Expense breakdown")
st.caption("Review the calculated amounts and compare them with the receipt.")
st.progress(1.0, text="Page 3 of 3 · Results")

if result is None:
    st.info("No calculation is available yet. Enter your items and calculate first.")
    if st.button("Go to item entry", type="primary"):
        st.switch_page("pages/2_Item_Entry.py")
    st.stop()

st.subheader("Bill breakdown")
subtotal_col, service_col, gst_col, total_col = st.columns(4)
subtotal_col.metric("Subtotal", f"SGD {result.subtotal:.2f}")
service_col.metric("Service charge", f"SGD {result.service_charge:.2f}")
gst_col.metric("GST", f"SGD {result.gst:.2f}")
total_col.metric("Calculated total", f"SGD {result.calculated_total:.2f}")

st.subheader("Per-person share")
for person, amount in result.per_person.items():
    st.write(f"**{person}** — SGD {amount:.2f}")

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
