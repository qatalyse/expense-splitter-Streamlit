"""Screen 1: bill setup and initial item-row count."""
from decimal import Decimal, InvalidOperation
import streamlit as st
from .state import BILLING_MODES, initialise_items, invalidate_result, parse_people

def render():
    st.subheader("1. Bill setup")
    st.text_input("Participants (comma-separated)", key="setup_people",
                  help="Names entered here become selectable on the next screen.")
    st.text_input("Receipt total in SGD (optional checksum)", key="setup_receipt")
    st.radio("Billing mode", list(BILLING_MODES), key="setup_mode")
    st.number_input("Initial number of items", min_value=1, max_value=100,
                    step=1, key="setup_count",
                    help="Starts at 3. Add or remove items freely on the next screen.")
    if st.button("Continue to items →", type="primary", use_container_width=True):
        try:
            people = parse_people(st.session_state.setup_people)
            receipt = st.session_state.setup_receipt.strip()
            if receipt:
                total = Decimal(receipt)
                if not total.is_finite() or total < 0:
                    raise ValueError("Receipt total must be a finite, non-negative number.")
            if st.session_state.setup_count < 1:
                raise ValueError("Enter at least one initial item.")
        except (InvalidOperation, ValueError) as exc:
            st.error(str(exc))
            return
        st.session_state.participants = people
        initialise_items(int(st.session_state.setup_count))
        for item in st.session_state.items:
            item["participants"] = [
                p for p in item["participants"] if p in people
            ]
        invalidate_result()
        st.session_state.step = 2
        st.rerun()
