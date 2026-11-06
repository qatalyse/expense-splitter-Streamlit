"""Page 1: bill setup, Google Sheets configuration and reusable People directory."""
from collections import Counter
from datetime import date

import streamlit as st

from database.google_sheets import GoogleSheetsSetupError
from database.sheets_repository import (
    add_person,
    archive_person,
    list_people,
    restore_person,
    update_person_name,
)
from ui.status import create_status_slot, flash_status, render_status
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
status = create_status_slot("setup_status")

st.session_state.setdefault("setup_expense_name", draft["expense_name"])
st.session_state.setdefault("setup_expense_date", draft["expense_date"])
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

# Database connection and initialization are managed from the Home page.
current_url = st.session_state.get("setup_spreadsheet_url", "").strip()
database_ready = (
    bool(current_url)
    and st.session_state.get("sheets_database_ready_url") == current_url
    and st.session_state.get("sheets_tested_url") == current_url
)

if database_ready:
    render_status(status, "success", "Google Sheets database is ready.")

    # Manage the reusable directory on the same setup page.
    st.divider()
    st.subheader("People directory")
    st.caption(
        "Add and rename people here. Archiving hides someone from future expenses "
        "without deleting their identity or historical records."
    )

    try:
        cache = st.session_state.get("people_directory_cache")
        if cache is None or cache.get("spreadsheet_url") != current_url:
            people = list_people(current_url, include_archived=True)
            cache = {"spreadsheet_url": current_url, "people": people}
            st.session_state["people_directory_cache"] = cache
        people = cache["people"]
    except (ValueError, GoogleSheetsSetupError) as exc:
        people = []
        render_status(status, "error", f"Could not load the People directory: {exc}")

    add_name_col, add_button_col = st.columns([3, 1])
    new_name = add_name_col.text_input(
        "New person's display name",
        key="setup_new_person_name",
        placeholder="e.g. Charlie",
    )
    if add_button_col.button(
        "Add person",
        key="add_person_button",
        use_container_width=True,
        disabled=not new_name.strip(),
    ):
        try:
            created_person = add_person(current_url, new_name)
            st.session_state.pop("people_directory_cache", None)
            st.session_state["setup_selected_person_ids"] = list(
                st.session_state.get("setup_selected_person_ids", [])
            ) + [created_person["person_id"]]
            flash_status("setup_status", "success", f"Added {created_person['display_name']} to People.")
            st.rerun()
        except (ValueError, GoogleSheetsSetupError) as exc:
            render_status(status, "error", str(exc))

    active_people = [person for person in people if person.get("is_active", True)]
    archived_people = [person for person in people if not person.get("is_active", True)]

    if active_people:
        with st.expander(f"Edit existing people ({len(active_people)})", expanded=False):
            for person in active_people:
                person_id = person["person_id"]
                with st.container(border=True):
                    edit_col, save_col, archive_col = st.columns([3, 1, 1])
                    edit_key = f"edit_person_name_{person_id}"
                    if edit_key not in st.session_state:
                        st.session_state[edit_key] = person["display_name"]
                    edit_col.text_input(
                        "Display name",
                        key=edit_key,
                        label_visibility="collapsed",
                    )
                    if save_col.button("Save", key=f"save_person_{person_id}"):
                        try:
                            update_person_name(
                                current_url,
                                person_id,
                                st.session_state[edit_key],
                            )
                            st.session_state.pop("people_directory_cache", None)
                            flash_status("setup_status", "success", "Display name updated. Historical expense names are unchanged.")
                            st.rerun()
                        except (ValueError, GoogleSheetsSetupError) as exc:
                            st.error(str(exc))
                    if archive_col.button("Archive", key=f"archive_person_{person_id}"):
                        try:
                            archive_person(current_url, person_id)
                            st.session_state.pop("people_directory_cache", None)
                            st.session_state["setup_selected_person_ids"] = [
                                value for value in st.session_state.get("setup_selected_person_ids", [])
                                if value != person_id
                            ]
                            flash_status("setup_status", "success", f"Archived {person['display_name']}.")
                            st.rerun()
                        except (ValueError, GoogleSheetsSetupError) as exc:
                            st.error(str(exc))

    if archived_people:
        with st.expander(f"Archived people ({len(archived_people)})", expanded=False):
            for person in archived_people:
                person_id = person["person_id"]
                restore_col, name_col = st.columns([1, 3])
                if restore_col.button("Restore", key=f"restore_person_{person_id}"):
                    try:
                        restore_person(current_url, person_id)
                        st.session_state.pop("people_directory_cache", None)
                        flash_status("setup_status", "success", f"Restored {person['display_name']}.")
                        st.rerun()
                    except (ValueError, GoogleSheetsSetupError) as exc:
                        st.error(str(exc))
                name_col.caption(f"{person['display_name']} · Archived")
            st.caption("Archived identities are retained for historical references.")

    # Participant selector uses permanent person IDs; calculations continue to
    # use the selected display names, with a name-to-ID map retained for saving.
    st.subheader("Participants for this expense")
    prior_person_ids = set(draft.get("participant_ids", []))
    archived_current_people = [
        person for person in archived_people
        if person["person_id"] in prior_person_ids
    ]
    selectable_people = active_people + archived_current_people
    active_by_id = {person["person_id"]: person for person in selectable_people}
    if "setup_selected_person_ids" not in st.session_state:
        prior_names = set(draft.get("participants", []))
        st.session_state["setup_selected_person_ids"] = [
            person["person_id"]
            for person in selectable_people
            if person["person_id"] in prior_person_ids
            or person["display_name"] in prior_names
        ]
    valid_selection = [
        person_id
        for person_id in st.session_state["setup_selected_person_ids"]
        if person_id in active_by_id
    ]
    if valid_selection != st.session_state["setup_selected_person_ids"]:
        st.session_state["setup_selected_person_ids"] = valid_selection

    active_name_counts = Counter(
        person["display_name"].strip().casefold()
        for person in active_people
    )

    def person_option_label(person_id: str) -> str:
        person = active_by_id[person_id]
        name = person["display_name"]
        suffix = " · Archived (existing expense)" if not person.get("is_active", True) else ""
        if active_name_counts[name.strip().casefold()] > 1:
            return f"{name} · {person_id[:8]}{suffix}"
        return f"{name}{suffix}"

    selected_ids = st.multiselect(
        "Select people sharing this bill",
        options=list(active_by_id),
        key="setup_selected_person_ids",
        format_func=person_option_label,
        placeholder="Select existing people",
    )
    selected_names = [active_by_id[person_id]["display_name"] for person_id in selected_ids]
    if len({name.casefold() for name in selected_names}) != len(selected_names):
        render_status(
            status,
            "warning",
            "Two selected people have the same display name. The current bill "
            "calculator identifies participants by display name, so select only "
            "one of them for this expense. Both identities remain in your directory.",
        )
else:
    render_status(status, "info", "Connect and initialize Google Sheets to use the reusable People directory.")
    st.subheader("Participants")
    participants_text = st.text_input(
        "Names separated by commas",
        key="setup_participants",
        help="For example: Alice, Bob, Charlie",
    )

if draft["items"]:
    st.caption(
        f"The current draft has {len(draft['items'])} item row(s). "
        "Changing the initial count will not silently delete existing rows."
    )

if st.button("Continue to item entry", type="primary", use_container_width=True):
    try:
        parse_optional_money(receipt_text, "Receipt total")
        if not isinstance(expense_date, date):
            raise ValueError("Select a valid expense date.")

        previous_person_id_by_name = draft.get("participant_id_by_name", {})
        if database_ready:
            ids = list(st.session_state.get("setup_selected_person_ids", []))
            selected = [active_by_id[person_id] for person_id in ids if person_id in active_by_id]
            participants = [person["display_name"].strip() for person in selected]
            if not participants:
                raise ValueError("Select at least one person or add someone to the People directory.")
            if len({name.casefold() for name in participants}) != len(participants):
                raise ValueError("Two selected people have the same display name. Rename one first.")
            draft["participant_id_by_name"] = {
                person["display_name"].strip(): person["person_id"]
                for person in selected
            }
            draft["participant_ids"] = ids
        else:
            participants = parse_participants(participants_text)
            draft.pop("participant_id_by_name", None)
            draft.pop("participant_ids", None)

        draft["expense_name"] = expense_name.strip()
        draft["expense_date"] = expense_date
        draft["participants"] = participants
        draft["receipt_total"] = receipt_text.strip()
        draft["billing_mode"] = billing_mode
        draft["initial_item_count"] = int(initial_count)
        draft["spreadsheet_url"] = current_url

        new_name_by_person_id = {
            person_id: name
            for name, person_id in draft.get("participant_id_by_name", {}).items()
        } if database_ready else {}

        for item in draft["items"]:
            rebased_participants = []
            for old_name in item["participants"]:
                person_id = previous_person_id_by_name.get(old_name)
                new_name = (
                    new_name_by_person_id.get(person_id)
                    if person_id else old_name
                )
                if new_name in participants and new_name not in rebased_participants:
                    rebased_participants.append(new_name)
            item["participants"] = rebased_participants
            widget_key = f"item_participants_{item['id']}"
            st.session_state[widget_key] = list(rebased_participants)

        while len(draft["items"]) < int(initial_count):
            draft["items"].append(new_item())

        if len(draft["items"]) > int(initial_count):
            render_status(
                status,
                "info",
                "Existing item rows have been preserved. Remove unwanted rows "
                "individually on the item-entry page.",
            )

        st.session_state.pop("calculated_result", None)
        st.session_state.pop("expense_save_bundle", None)
        st.session_state.pop("expense_saved", None)
        st.switch_page("pages/2_Item_Entry.py")
    except ValueError as exc:
        st.error(str(exc))


if st.button("← Home", use_container_width=True):
    st.switch_page("pages/0_Home.py")
