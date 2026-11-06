"""Application entry point and three-page navigation."""
import streamlit as st

st.set_page_config(page_title="Expense Splitter", page_icon="🧾", layout="centered")

setup_page = st.Page("pages/1_Bill_Setup.py", title="Bill setup", default=True)
items_page = st.Page("pages/2_Item_Entry.py", title="Item entry")
results_page = st.Page("pages/3_Results.py", title="Results")

navigation = st.navigation([setup_page, items_page, results_page], position="hidden")
navigation.run()
