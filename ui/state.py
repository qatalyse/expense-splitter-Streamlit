"""UI draft lifecycle and stable item identities."""
from uuid import uuid4
import streamlit as st

BILLING_MODES = {
    "GST + service charge": (True, True, False),
    "GST only": (True, False, False),
    "Service charge only": (False, True, False),
    "Nett (no additional charges)": (False, False, True),
}

def new_item():
    return {"id": uuid4().hex, "name": "", "price": "", "participants": []}

def init_state():
    defaults = {
        "step": 1,
        "setup_people": "Alice, Bob",
        "setup_receipt": "",
        "setup_mode": "GST + service charge",
        "setup_count": 3,
        "participants": [],
        "items": [],
        "items_initialised": False,
        "result": None,
        "calculated_bill": None,
        "confirm_reset": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset_draft():
    for key in ("step", "setup_people", "setup_receipt", "setup_mode",
                "setup_count", "participants", "items", "items_initialised",
                "result", "calculated_bill", "confirm_reset"):
        st.session_state.pop(key, None)
    init_state()

def parse_people(raw):
    people = [p.strip() for p in raw.split(",") if p.strip()]
    if not people:
        raise ValueError("Enter at least one participant.")
    if len(set(p.casefold() for p in people)) != len(people):
        raise ValueError("Participant names must be unique (ignoring case).")
    return people

def initialise_items(count):
    if not st.session_state.items_initialised:
        st.session_state.items = [new_item() for _ in range(count)]
        st.session_state.items_initialised = True

def invalidate_result():
    st.session_state.result = None
    st.session_state.calculated_bill = None

def add_item():
    st.session_state.items.append(new_item())
    invalidate_result()

def remove_item(item_id):
    st.session_state.items = [
        item for item in st.session_state.items if item["id"] != item_id
    ]
    invalidate_result()
