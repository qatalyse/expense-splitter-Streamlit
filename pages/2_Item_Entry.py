"""Page 2: dynamically add, edit and remove item rows."""
import streamlit as st

from expense_splitter import split_expense
from pages.common import (
    add_item,
    build_bill_from_draft,
    ensure_draft,
    remove_item,
    sync_item_widgets,
)

draft = ensure_draft()
participants = draft["participants"]

st.title("Enter items")
st.caption("Add each receipt item and select everyone sharing that item.")
st.progress(2 / 3, text="Page 2 of 3 · Item entry")

if not participants:
    st.warning("No participants are configured.")
    if st.button("Return to bill setup"):
        st.switch_page("pages/1_Bill_Setup.py")
    st.stop()

st.caption(
    f"Participants: {', '.join(participants)} · "
    f"Billing mode: {draft['billing_mode']}"
)

for index, item in enumerate(list(draft["items"]), start=1):
    item_id = item["id"]
    name_key = f"item_name_{item_id}"
    price_key = f"item_price_{item_id}"
    participants_key = f"item_participants_{item_id}"

    if name_key not in st.session_state:
        st.session_state[name_key] = item.get("name", "")
    if price_key not in st.session_state:
        st.session_state[price_key] = item.get("price", "")
    if participants_key not in st.session_state:
        st.session_state[participants_key] = [
            person for person in item.get("participants", [])
            if person in participants
        ]

    with st.container(border=True):
        heading_col, remove_col = st.columns([5, 1])
        heading_col.markdown(f"**Item {index}**")
        remove_col.button(
            "Remove",
            key=f"remove_item_{item_id}",
            help="Remove this item row",
            on_click=remove_item,
            args=(item_id,),
        )

        name_col, price_col = st.columns([2, 1])
        name_col.text_input(
            "Item name",
            key=name_key,
            placeholder="e.g. Soba",
            on_change=sync_item_widgets,
        )
        price_col.text_input(
            "Price (SGD)",
            key=price_key,
            placeholder="e.g. 12.00",
            on_change=sync_item_widgets,
        )
        st.multiselect(
            "Who is sharing this item?",
            options=participants,
            key=participants_key,
            on_change=sync_item_widgets,
            placeholder="Select one or more participants",
        )

st.button(
    "+ Add another item",
    key="add_item",
    on_click=add_item,
    use_container_width=True,
)

st.divider()
back_col, calculate_col = st.columns(2)

if back_col.button("← Back to bill setup", use_container_width=True):
    sync_item_widgets()
    st.switch_page("pages/1_Bill_Setup.py")

if calculate_col.button("Calculate expense", type="primary", use_container_width=True):
    try:
        sync_item_widgets()
        bill = build_bill_from_draft()
        st.session_state.pop("expense_save_bundle", None)
        st.session_state.pop("expense_saved_id", None)
        st.session_state.calculated_result = split_expense(bill)
        st.switch_page("pages/3_Results.py")
    except (ValueError, ArithmeticError) as exc:
        st.error(str(exc))
