"""Streamlit UI; business logic lives in expense_splitter/."""
from decimal import Decimal, InvalidOperation
import streamlit as st
from expense_splitter import Bill, BillingRules, Item, split_expense

st.set_page_config(page_title="Expense Splitter", page_icon="🧾", layout="centered")
st.title("Expense Splitter")
st.caption("Split an itemised bill and compare the calculated total with the receipt.")

with st.form("expense_form"):
    st.subheader("Receipt and participants")
    receipt_text = st.text_input("Receipt total in SGD (optional checksum)", placeholder="41.97")
    people_text = st.text_input("Participants, separated by commas", value="Alice, Bob")
    st.subheader("Billing rules")
    nett = st.toggle("Prices are already nett (do not add GST/service charge)")
    gst_on = st.checkbox("Apply GST (9%)", value=True, disabled=nett)
    service_on = st.checkbox("Apply service charge (10%)", value=True, disabled=nett)
    st.subheader("Items")
    st.caption("For shared items, list all participants sharing that item.")
    count = st.number_input("Number of item rows", min_value=1, max_value=30, value=3, step=1)
    rows = []
    for index in range(int(count)):
        st.markdown(f"**Item {index + 1}**")
        left, right = st.columns([2, 1])
        name = left.text_input("Name", key=f"name_{index}", placeholder="Soba")
        price = right.text_input("Price (SGD)", key=f"price_{index}", placeholder="12.00")
        assigned = st.text_input("Assigned participants", key=f"assigned_{index}", value=people_text)
        rows.append((name, price, assigned))
    submitted = st.form_submit_button("Calculate", type="primary", use_container_width=True)

if submitted:
    try:
        people = [p.strip() for p in people_text.split(",") if p.strip()]
        if not people:
            raise ValueError("Enter at least one participant.")
        items = []
        for index, (name, price_text, assigned_text) in enumerate(rows, start=1):
            if not name.strip() and not price_text.strip():
                continue
            if not name.strip() or not price_text.strip():
                raise ValueError(f"Complete both name and price for item {index}.")
            try:
                price = Decimal(price_text.strip())
            except InvalidOperation as exc:
                raise ValueError(f"Item {index} price must be numeric.") from exc
            assigned = [p.strip() for p in assigned_text.split(",") if p.strip()]
            unknown = sorted(set(assigned) - set(people))
            if unknown:
                raise ValueError(f"Item {index} contains unlisted participant(s): {', '.join(unknown)}.")
            items.append(Item(name.strip(), price, assigned))
        if not items:
            raise ValueError("Add at least one item.")
        try:
            receipt = Decimal(receipt_text.strip()) if receipt_text.strip() else None
        except InvalidOperation as exc:
            raise ValueError("Receipt total must be numeric.") from exc
        if receipt is not None and receipt < 0:
            raise ValueError("Receipt total cannot be negative.")

        result = split_expense(Bill(items, BillingRules(
            gst_enabled=gst_on, service_charge_enabled=service_on, prices_are_nett=nett
        ), receipt))
        st.subheader("Bill breakdown")
        cols = st.columns(4)
        cols[0].metric("Subtotal", f"SGD {result.subtotal:.2f}")
        cols[1].metric("Service", f"SGD {result.service_charge:.2f}")
        cols[2].metric("GST", f"SGD {result.gst:.2f}")
        cols[3].metric("Calculated total", f"SGD {result.calculated_total:.2f}")
        st.subheader("Per-person amount")
        for person, amount in result.per_person.items():
            st.write(f"**{person}** — SGD {amount:.2f}")
        if result.receipt_total is None:
            st.info("Checksum skipped because no receipt total was entered.")
        elif result.reconciled:
            st.success(f"Receipt matches within SGD 0.01. Receipt total: SGD {result.receipt_total:.2f}")
        else:
            st.warning(f"Receipt total SGD {result.receipt_total:.2f}; difference SGD {result.difference:+.2f}. Check items, discounts and POS rounding.")
        st.caption("MVP: discounts, vouchers and advanced POS rounding policies are not implemented.")
    except (ValueError, InvalidOperation, ArithmeticError) as exc:
        st.error(str(exc))
