"""Reusable expense breakdown presentation for new and historical expenses."""
from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from expense_splitter.models import SplitResult
from presentation.share_format import format_all_message, format_person_message


def render_expense_breakdown(
    expense_name: str,
    expense_date: date,
    result: SplitResult,
    *,
    show_totals: bool = True,
) -> None:
    """Render the item/person matrix and the same copyable text in any workflow."""
    people = list(result.per_person)

    if show_totals:
        st.subheader("Bill total")
        st.metric("Calculated total", f"SGD {result.calculated_total:.2f}")

    st.subheader("Itemised allocation")
    st.caption(
        "Each cell shows that person's share of the item, including applicable charges."
    )
    table_rows = []
    for allocation in result.item_allocations:
        row = {"Item": allocation.item_name}
        for person in people:
            amount = allocation.per_person.get(person)
            row[person] = f"SGD {amount:.2f}" if amount is not None else "—"
        row["Item total"] = f"SGD {allocation.total:.2f}"
        table_rows.append(row)

    total_row = {"Item": "TOTAL OWED"}
    for person in people:
        total_row[person] = f"SGD {result.per_person[person]:.2f}"
    total_row["Item total"] = f"SGD {result.calculated_total:.2f}"
    table_rows.append(total_row)
    st.table(pd.DataFrame(table_rows, columns=["Item", *people, "Item total"]))

    st.subheader("Copy breakdown for group chats")
    st.caption(
        "Copy an individual participant's message or the complete breakdown. "
        "The text includes WhatsApp monospace markers."
    )
    for person, amount in result.per_person.items():
        with st.expander(f"{person} · SGD {amount:.2f}", expanded=False):
            message = format_person_message(
                expense_name,
                expense_date,
                person,
                result.item_allocations,
                amount,
            )
            st.code(message, language="text")

    all_message = format_all_message(
        expense_name,
        expense_date,
        result.per_person,
        result.item_allocations,
        result.calculated_total,
    )
    st.markdown("**All participants**")
    st.code(all_message, language="text")
