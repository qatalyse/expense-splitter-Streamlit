"""Application entry point and navigation."""
import streamlit as st

st.set_page_config(page_title="Expense Splitter", page_icon="🧾", layout="centered")

home_page = st.Page("pages/0_Home.py", title="Home", default=True)
setup_page = st.Page("pages/1_Bill_Setup.py", title="Bill setup")
items_page = st.Page("pages/2_Item_Entry.py", title="Item entry")
results_page = st.Page("pages/3_Results.py", title="Results")
history_page = st.Page("pages/4_Expense_History.py", title="Expense history")
detail_page = st.Page("pages/5_Expense_Detail.py", title="Saved expense")

navigation = st.navigation(
    [home_page, setup_page, items_page, results_page, history_page, detail_page],
    position="hidden",
)
navigation.run()
