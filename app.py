"""Three-screen Streamlit application; calculation stays in expense_splitter."""
import streamlit as st
from ui import setup, items, results
from ui.state import init_state, reset_draft

st.set_page_config(page_title="Expense Splitter", page_icon="🧾", layout="centered")
init_state()
st.title("Expense Splitter")
step = st.session_state.step
st.caption(f"Step {step} of 3 · " + {1: "Bill setup", 2: "Enter items", 3: "Results"}[step])
st.progress(step / 3)
if step == 1:
    setup.render()
elif step == 2:
    items.render()
else:
    results.render()

st.divider()
if not st.session_state.confirm_reset:
    if st.button("Start over / Reset", key="reset_request"):
        st.session_state.confirm_reset = True
        st.rerun()
else:
    st.warning("Discard the current draft and results?")
    left, right = st.columns(2)
    if left.button("Yes, reset", type="primary"):
        reset_draft()
        st.rerun()
    if right.button("Cancel"):
        st.session_state.confirm_reset = False
        st.rerun()
