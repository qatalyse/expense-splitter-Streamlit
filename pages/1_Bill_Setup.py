"""Page 1: bill setup and Google Sheets connection/database setup."""
from datetime import date

import streamlit as st

from database.google_sheets import (
    GoogleSheetsSetupError,
    initialize_database,
    test_connection,
)
from pages.common import (
    BILLING_MODES,
    ensure_draft,
    new_item,
    parse_optional_money,
    parse_participants,
)

draft = ensure_draft()

st.title("Bill setup")
st.caption("Set up the expense, people and billing details before entering items.")
st.progress(1 / 3, text="Page 1 of 3 · Bill setup")

st.session_state.setdefault("setup_expense_name", draft["expense_name"])
st.session_state.setdefault("setup_expense_date", draft["expense_date"])
st.session_state.setdefault("setup_participants", ", ".join(draft["participants"]))
st.session_state.setdefault("setup_receipt_total", draft["receipt_total"])
st.session_state.setdefault("setup_billing_mode", draft["billing_mode"])
st.session_state.setdefault(
    "setup_initial_item_count",
    max(1, int(draft["initial_item_count"])),
)

try:
    default_spreadsheet_url = st.secrets.get("google_sheets", {}).get(
        "spreadsheet_url", ""
    )
except (FileNotFoundError, KeyError, RuntimeError):
    default_spreadsheet_url = ""

st.session_state.setdefault("setup_spreadsheet_url", default_spreadsheet_url)

st.subheader("Expense details")
expense_name = st.text_input(
    "Expense name (optional)",
    key="setup_expense_name",
    placeholder="e.g. Dinner at Restaurant",
)
expense_date = st.date_input(
    "Expense date",
    key="setup_expense_date",
    help="Defaults to today's date in Singapore.",
)

st.subheader("Participants")
participants_text = st.text_input(
    "Names separated by commas",
    key="setup_participants",
    help="For example: Alice, Bob, Charlie",
)

st.subheader("Receipt")
receipt_text = st.text_input(
    "Receipt total in SGD (optional)",
    key="setup_receipt_total",
    placeholder="e.g. 41.97",
    help="Used to compare the calculated total with the POS amount.",
)

st.subheader("Billing mode")
billing_mode = st.radio(
    "Select the billing treatment",
    options=BILLING_MODES,
    key="setup_billing_mode",
    help=(
        "GST defaults to 9% and service charge defaults to 10%. "
        "Nett treats entered item prices as final and adds no further charges."
    ),
)

st.subheader("Initial number of items")
initial_count = st.number_input(
    "How many item rows should be created?",
    min_value=1,
    max_value=100,
    step=1,
    key="setup_initial_item_count",
    help="Defaults to 3. You can add or remove rows on the next page.",
)

# Database connection controls are intentionally on Page 1, below item count.
st.divider()
st.subheader("Google Sheets database")
st.caption(
    "Connect a spreadsheet to initialize the database now. "
    "Your service-account credentials stay on the server."
)
spreadsheet_url = st.text_input(
    "Google Sheets URL",
    key="setup_spreadsheet_url",
    placeholder="https://docs.google.com/spreadsheets/d/...",
    help=(
        "Share the spreadsheet with your service-account email as Editor. "
        "The URL identifies the spreadsheet; it is not an authentication secret."
    ),
)

last_connection = st.session_state.get("sheets_connection")
tested_url = st.session_state.get("sheets_tested_url")
if last_connection and tested_url == spreadsheet_url.strip():
    st.success(
        f"Connected to **{last_connection['title']}**. "
        f"Found {len(last_connection['sheets'])} existing tab(s)."
    )
elif last_connection or tested_url:
    st.info("The spreadsheet URL changed. Test the new URL before initializing it.")

test_col, initialize_col = st.columns(2)
with test_col:
    test_clicked = st.button(
        "Test connection",
        use_container_width=True,
        disabled=not spreadsheet_url.strip(),
    )
with initialize_col:
    initialize_clicked = st.button(
        "Initialize database",
        type="primary",
        use_container_width=True,
        disabled=not spreadsheet_url.strip(),
        help="Creates the four required tabs and headers. Existing data is not overwritten.",
    )

if test_clicked:
    st.session_state.pop("sheets_connection", None)
    st.session_state.pop("sheets_tested_url", None)
    try:
        connection = test_connection(spreadsheet_url)
        st.session_state["sheets_connection"] = connection
        st.session_state["sheets_tested_url"] = spreadsheet_url.strip()
        st.success(
            f"Connection successful: **{connection['title']}**. "
            f"Existing tabs: {', '.join(connection['sheets']) or 'none'}."
        )
    except (ValueError, GoogleSheetsSetupError) as exc:
        st.error(str(exc))

if initialize_clicked:
    if st.session_state.get("sheets_tested_url") != spreadsheet_url.strip():
        st.warning("Test this spreadsheet connection successfully before initializing it.")
    else:
        try:
            setup_result = initialize_database(spreadsheet_url)
            st.session_state["sheets_database_ready_url"] = spreadsheet_url.strip()
            created = setup_result["created_tabs"]
            if created:
                st.success(
                    "Database initialized. Created tabs: " + ", ".join(created) + "."
                )
            else:
                st.success(
                    "Database is ready. All four tabs and headers already exist."
                )
        except (ValueError, GoogleSheetsSetupError) as exc:
            st.error(str(exc))

if st.session_state.get("sheets_database_ready_url") == spreadsheet_url.strip():
    st.success("Database structure is initialized and ready for expense records.")

if draft["items"]:
    st.caption(
        f"The current draft has {len(draft['items'])} item row(s). "
        "Changing the initial count will not silently delete existing rows."
    )

if st.button("Continue to item entry", type="primary", use_container_width=True):
    try:
        participants = parse_participants(participants_text)
        parse_optional_money(receipt_text, "Receipt total")
        if not isinstance(expense_date, date):
            raise ValueError("Select a valid expense date.")

        draft["expense_name"] = expense_name.strip()
        draft["expense_date"] = expense_date
        draft["participants"] = participants
        draft["receipt_total"] = receipt_text.strip()
        draft["billing_mode"] = billing_mode
        draft["initial_item_count"] = int(initial_count)
        draft["spreadsheet_url"] = spreadsheet_url.strip()

        for item in draft["items"]:
            item["participants"] = [
                person for person in item["participants"] if person in participants
            ]

        while len(draft["items"]) < int(initial_count):
            draft["items"].append(new_item())

        if len(draft["items"]) > int(initial_count):
            st.info(
                "Existing item rows have been preserved. Remove unwanted rows "
                "individually on the item-entry page."
            )

        st.switch_page("pages/2_Item_Entry.py")
    except ValueError as exc:
        st.error(str(exc))
