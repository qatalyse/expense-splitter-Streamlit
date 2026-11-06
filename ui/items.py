"""Screen 2: dynamic item entry and calculation."""
from decimal import Decimal, InvalidOperation
import streamlit as st
from expense_splitter import Bill, BillingRules, Item, split_expense
from .state import BILLING_MODES, add_item, invalidate_result, remove_item

def _sync_item(item_id):
    item = next(row for row in st.session_state.items if row["id"] == item_id)
    item["name"] = st.session_state[f"name_{item_id}"]
    item["price"] = st.session_state[f"price_{item_id}"]
    item["participants"] = st.session_state[f"pax_{item_id}"]
    invalidate_result()

def _calculate():
    try:
        parsed = []
        for index, item in enumerate(st.session_state.items, 1):
            if not item["name"].strip() and not item["price"].strip():
                continue
            if not item["name"].strip() or not item["price"].strip():
                raise ValueError(f"Complete the name and price for item {index}.")
            price = Decimal(item["price"].strip())
            if not price.is_finite() or price < 0:
                raise ValueError(f"Item {index} needs a finite, non-negative price.")
            if not item["participants"]:
                raise ValueError(f"Assign at least one participant to item {index}.")
            parsed.append(Item(item["name"].strip(), price, item["participants"]))
        if not parsed:
            raise ValueError("Add at least one completed item.")
        receipt_text = st.session_state.setup_receipt.strip()
        receipt = Decimal(receipt_text) if receipt_text else None
        gst, service, nett = BILLING_MODES[st.session_state.setup_mode]
        bill = Bill(
            items=parsed,
            billing=BillingRules(gst_enabled=gst, service_charge_enabled=service,
                                 prices_are_nett=nett),
            receipt_total=receipt,
        )
        result = split_expense(bill)
        st.session_state.calculated_bill = bill
        st.session_state.result = result
        st.session_state.step = 3
        st.rerun()
    except (ValueError, InvalidOperation, ArithmeticError) as exc:
        st.error(str(exc))

def render():
    st.subheader("2. Enter items")
    st.caption("Select participants from the list set up on the previous screen.")
    for index, item in enumerate(st.session_state.items, 1):
        item_id = item["id"]
        with st.container(border=True):
            heading, delete = st.columns([5, 1])
            heading.markdown(f"**Item {index}**")
            if delete.button("✕", key=f"remove_{item_id}", help="Remove this item"):
                remove_item(item_id)
                st.rerun()
            left, right = st.columns([2, 1])
            left.text_input("Item name", value=item["name"], key=f"name_{item_id}",
                            on_change=_sync_item, args=(item_id,))
            right.text_input("Price (SGD)", value=item["price"], key=f"price_{item_id}",
                             on_change=_sync_item, args=(item_id,))
            st.multiselect("Who shares this item?", options=st.session_state.participants,
                           default=item["participants"], key=f"pax_{item_id}",
                           on_change=_sync_item, args=(item_id,))
    st.button("＋ Add another item", on_click=add_item, use_container_width=True)
    back, next_button = st.columns(2)
    if back.button("← Back to setup", use_container_width=True):
        st.session_state.step = 1
        st.rerun()
    with next_button:
        if st.button("Calculate →", type="primary", use_container_width=True):
            _calculate()
