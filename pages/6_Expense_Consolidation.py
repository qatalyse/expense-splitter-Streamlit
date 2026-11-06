"""Combine one person's saved shares across selected expenses."""
from decimal import Decimal

import streamlit as st

from database.google_sheets import GoogleSheetsSetupError
from database.sheets_repository import (
    get_combined_person_expenses,
    list_people,
    list_person_expense_summaries,
)
from presentation.share_format import format_combined_person_message
from ui.status import create_status_slot, render_status

st.title("Consolidate expenses")
status = create_status_slot("consolidation_status")

spreadsheet_url = st.session_state.get("setup_spreadsheet_url", "").strip()
if not spreadsheet_url:
    try:
        spreadsheet_url = st.secrets.get("google_sheets", {}).get(
            "spreadsheet_url", ""
        ).strip()
    except (FileNotFoundError, KeyError, RuntimeError):
        spreadsheet_url = ""

if not spreadsheet_url:
    render_status(status, "warning", "No Google Sheets URL is configured.")
    if st.button("← Home"):
        st.switch_page("pages/0_Home.py")
    st.stop()

include_archived = st.checkbox(
    "Include archived expenses",
    key="consolidation_include_archived",
)

try:
    people_cache_key = ("consolidation_people", spreadsheet_url)
    if people_cache_key not in st.session_state:
        st.session_state[people_cache_key] = list_people(spreadsheet_url)
    people = st.session_state[people_cache_key]
except (ValueError, GoogleSheetsSetupError) as exc:
    render_status(status, "error", f"Could not load People: {exc}")
    st.stop()

if not people:
    render_status(status, "info", "There are no active people in the People directory.")
    if st.button("← Home"):
        st.switch_page("pages/0_Home.py")
    st.stop()

people_by_id = {person["person_id"]: person for person in people}
person_id = st.selectbox(
    "Person",
    options=list(people_by_id),
    format_func=lambda value: people_by_id[value]["display_name"],
    key="consolidation_person_id",
    placeholder="Select a person",
)

if person_id:
    selected_person = people_by_id[person_id]
    person_name = selected_person["display_name"]
    summary_cache_key = (
        "consolidation_summaries",
        spreadsheet_url,
        person_id,
        include_archived,
    )

    refresh_col, _ = st.columns([1, 3])
    if refresh_col.button("Refresh expenses"):
        st.session_state.pop(summary_cache_key, None)
        st.session_state.pop("consolidation_message", None)
        st.rerun()

    try:
        if summary_cache_key not in st.session_state:
            with st.spinner("Finding expenses for this person..."):
                st.session_state[summary_cache_key] = list_person_expense_summaries(
                    spreadsheet_url,
                    person_id,
                    include_archived=include_archived,
                )
        summaries = st.session_state[summary_cache_key]
    except (ValueError, GoogleSheetsSetupError) as exc:
        render_status(status, "error", f"Could not retrieve this person's expenses: {exc}")
        summaries = []

    st.subheader(f"Expenses involving {person_name}")
    if not summaries:
        render_status(status, "info", "No saved expenses were found for this person.")
    else:
        summary_by_id = {
            row["expense_id"]: row for row in summaries
        }

        def expense_label(expense_id: str) -> str:
            row = summary_by_id[expense_id]
            archived = str(row.get("is_archived", "FALSE")).casefold() in {
                "true", "1", "yes"
            }
            marker = " · Archived" if archived else ""
            return (
                f"{row.get('expense_date', '')} · "
                f"{row.get('expense_name', 'Expense')} · "
                f"SGD {Decimal(row['person_share']):.2f}{marker}"
            )

        selected_expense_ids = st.multiselect(
            "Select expenses to combine",
            options=[row["expense_id"] for row in summaries],
            format_func=expense_label,
            key="consolidation_selected_expenses",
            placeholder="Choose one or more expenses",
        )

        if selected_expense_ids:
            selected_total = sum(
                (
                    Decimal(summary_by_id[expense_id]["person_share"])
                    for expense_id in selected_expense_ids
                ),
                Decimal("0.00"),
            )
            st.metric(
                "Combined amount owed",
                f"SGD {selected_total:.2f}",
                help="Sum of this person's stored final allocations across the selected expenses.",
            )

        selection_signature = (person_id, tuple(selected_expense_ids))
        generated = st.session_state.get("consolidation_message")
        message_matches_selection = (
            generated is not None
            and generated.get("selection") == selection_signature
        )

        if st.button(
            "Generate WhatsApp message",
            type="primary",
            use_container_width=True,
            disabled=not selected_expense_ids,
        ):
            try:
                with st.spinner("Preparing combined breakdown..."):
                    combined_expenses = get_combined_person_expenses(
                        spreadsheet_url,
                        person_id,
                        person_name,
                        selected_expense_ids,
                    )
                    message = format_combined_person_message(
                        person_name,
                        combined_expenses,
                    )
                st.session_state["consolidation_message"] = {
                    "selection": selection_signature,
                    "message": message,
                }
                st.rerun()
            except (ValueError, GoogleSheetsSetupError) as exc:
                render_status(status, "error", str(exc))

        if message_matches_selection:
            st.subheader("WhatsApp message")
            st.caption(
                "Use the copy control on the code block to copy the complete "
                "monospace message."
            )
            st.code(generated["message"], language="text")
        elif generated is not None:
            st.session_state.pop("consolidation_message", None)

if st.button("← Home", use_container_width=True):
    st.switch_page("pages/0_Home.py")
