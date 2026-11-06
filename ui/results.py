"""Screen 3: results and explicit persistence placeholder."""
import streamlit as st

def render():
    st.subheader("3. Results")
    result = st.session_state.result
    if result is None:
        st.info("No current calculation. Enter items and calculate first.")
        if st.button("← Go to items"):
            st.session_state.step = 2
            st.rerun()
        return
    st.metric("Calculated total", f"SGD {result.calculated_total:.2f}")
    a, b, c = st.columns(3)
    a.metric("Subtotal", f"SGD {result.subtotal:.2f}")
    b.metric("Service charge", f"SGD {result.service_charge:.2f}")
    c.metric("GST", f"SGD {result.gst:.2f}")
    st.subheader("Per-person amounts")
    for person, amount in result.per_person.items():
        st.write(f"**{person}** — SGD {amount:.2f}")
    if result.receipt_total is None:
        st.info("Receipt checksum skipped.")
    elif result.reconciled:
        st.success(f"Receipt matches within SGD 0.01 (SGD {result.receipt_total:.2f}).")
    else:
        st.warning(f"Receipt: SGD {result.receipt_total:.2f}; difference: SGD {result.difference:+.2f}.")
    st.button("Save to database (coming later)", disabled=True, use_container_width=True,
              help="Database persistence is not implemented yet; nothing is saved.")
    if st.button("← Edit items", use_container_width=True):
        st.session_state.step = 2
        st.rerun()
