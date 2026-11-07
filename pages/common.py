"""Shared session-state and input helpers for the Streamlit pages."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from zoneinfo import ZoneInfo

import streamlit as st

from expense_splitter import Bill, BillingRules, Item

SPREADSHEET_URL_STATE_KEY = "app_spreadsheet_url"


def get_spreadsheet_url() -> str:
    """Return the session-wide spreadsheet URL.

    The app-owned key survives navigation between Streamlit pages. The legacy
    setup_spreadsheet_url key is accepted as a migration fallback for sessions
    created before this helper was introduced.
    """
    url = str(st.session_state.get(SPREADSHEET_URL_STATE_KEY, "") or "").strip()
    if url:
        return url

    legacy_url = str(st.session_state.get("setup_spreadsheet_url", "") or "").strip()
    if legacy_url:
        st.session_state[SPREADSHEET_URL_STATE_KEY] = legacy_url
        return legacy_url
    return ""


def set_spreadsheet_url(value: str) -> str:
    """Persist a UI-provided URL independently of any page-scoped widget."""
    url = str(value or "").strip()
    previous = get_spreadsheet_url()
    st.session_state[SPREADSHEET_URL_STATE_KEY] = url

    if previous != url:
        # Connection and schema readiness only apply to the URL that was tested.
        for key in (
            "sheets_connection",
            "sheets_tested_url",
            "sheets_database_ready_url",
            "people_directory_cache",
        ):
            st.session_state.pop(key, None)
        for key in list(st.session_state.keys()):
            if key.startswith(("consolidation_people::", "consolidation_summaries::")):
                st.session_state.pop(key, None)
        st.session_state.pop("consolidation_message", None)
    return url


BILLING_MODES = (
    "GST + service charge",
    "GST only",
    "Service charge only",
    "Nett",
)


def new_item() -> dict:
    """Return a blank draft item with an ID stable across reruns."""
    return {"id": str(uuid4()), "name": "", "price": "", "participants": []}


def singapore_today() -> date:
    """Return today's date in Singapore, independent of server timezone."""
    return datetime.now(ZoneInfo("Asia/Singapore")).date()


def ensure_draft() -> dict:
    """Initialise the current bill once per Streamlit session."""
    if "expense_draft" not in st.session_state:
        st.session_state.expense_draft = {
            "expense_name": "",
            "expense_date": singapore_today(),
            "participants": ["Alice", "Bob"],
            "receipt_total": "",
            "billing_mode": BILLING_MODES[0],
            "initial_item_count": 3,
            "items": [],
        }
    return st.session_state.expense_draft


def sync_item_widgets() -> None:
    """Copy visible item-widget values into the durable session draft."""
    draft = ensure_draft()
    for item in draft["items"]:
        item_id = item["id"]
        item["name"] = st.session_state.get(f"item_name_{item_id}", item.get("name", ""))
        item["price"] = st.session_state.get(f"item_price_{item_id}", item.get("price", ""))
        item["participants"] = st.session_state.get(
            f"item_participants_{item_id}", item.get("participants", [])
        )
    st.session_state.pop("calculated_result", None)
    st.session_state.pop("expense_save_bundle", None)
    st.session_state.pop("expense_saved_id", None)


def add_item() -> None:
    """Preserve existing rows and append one blank row."""
    sync_item_widgets()
    ensure_draft()["items"].append(new_item())


def remove_item(item_id: str) -> None:
    """Preserve existing rows, then remove only the requested item ID."""
    sync_item_widgets()
    draft = ensure_draft()
    draft["items"] = [item for item in draft["items"] if item["id"] != item_id]


def parse_participants(raw_value: str) -> list[str]:
    """Parse comma-separated names and reject missing or duplicate entries."""
    participants = [name.strip() for name in raw_value.split(",") if name.strip()]
    if not participants:
        raise ValueError("Enter at least one participant.")
    normalised = [name.casefold() for name in participants]
    if len(normalised) != len(set(normalised)):
        raise ValueError("Participant names must be unique.")
    return participants


def parse_optional_money(raw_value: str, label: str) -> Decimal | None:
    """Parse an optional, finite, non-negative SGD amount."""
    value = raw_value.strip()
    if not value:
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a valid amount.") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{label} must be a finite, non-negative amount.")
    return amount.quantize(Decimal("0.01"))


def billing_rules_for_mode(mode: str) -> BillingRules:
    """Translate the setup-page selection into calculation-layer rules."""
    if mode == "GST + service charge":
        return BillingRules(gst_enabled=True, service_charge_enabled=True)
    if mode == "GST only":
        return BillingRules(gst_enabled=True, service_charge_enabled=False)
    if mode == "Service charge only":
        return BillingRules(gst_enabled=False, service_charge_enabled=True)
    if mode == "Nett":
        return BillingRules(
            gst_enabled=False,
            service_charge_enabled=False,
            prices_are_nett=True,
        )
    raise ValueError("Select a valid billing mode.")


def build_bill_from_draft() -> Bill:
    """Validate the draft and construct the domain Bill."""
    draft = ensure_draft()
    participants = draft["participants"]
    items: list[Item] = []

    for index, raw_item in enumerate(draft["items"], start=1):
        name = str(raw_item.get("name", "")).strip()
        price_text = str(raw_item.get("price", "")).strip()
        assigned = list(raw_item.get("participants", []))

        if not name and not price_text and not assigned:
            raise ValueError(f"Item {index} is empty. Remove the row or complete it.")
        if not name:
            raise ValueError(f"Enter a name for item {index}.")
        if not price_text:
            raise ValueError(f"Enter a price for item {index}.")
        try:
            price = Decimal(price_text)
        except InvalidOperation as exc:
            raise ValueError(f"Price for item {index} must be numeric.") from exc
        if not price.is_finite() or price < 0:
            raise ValueError(f"Price for item {index} must be finite and non-negative.")
        if not assigned:
            raise ValueError(f"Assign at least one participant to {name!r}.")
        unknown = sorted(set(assigned) - set(participants))
        if unknown:
            raise ValueError(
                f"Item {index} contains unlisted participant(s): {', '.join(unknown)}."
            )
        items.append(Item(name, price.quantize(Decimal("0.01")), assigned))

    if not items:
        raise ValueError("Add at least one item.")

    return Bill(
        items=items,
        billing=billing_rules_for_mode(draft["billing_mode"]),
        receipt_total=parse_optional_money(draft["receipt_total"], "Receipt total"),
        expense_name=draft.get("expense_name", ""),
        expense_date=draft.get("expense_date"),
    )


def clear_draft() -> None:
    """Clear draft, calculation and page widget keys before a new expense."""
    prefixes = ("setup_", "item_name_", "item_price_", "item_participants_")
    for key in list(st.session_state.keys()):
        if key in {
            "expense_draft", "calculated_result", "confirm_reset",
            "expense_save_bundle", "expense_saved_id",
        } or (key.startswith(prefixes) and key != "setup_spreadsheet_url"):
            st.session_state.pop(key, None)
