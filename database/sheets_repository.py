"""Repository operations for People and expense records in Google Sheets."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from database.google_sheets import (
    SHEET_SCHEMA,
    GoogleSheetsSetupError,
    _sheets_service,
    _translate_api_error,
    extract_spreadsheet_id,
)

CENT = Decimal("0.01")
CALCULATION_VERSION = "1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_table(service, spreadsheet_id: str, tab: str) -> list[dict]:
    """Read a tab as dictionaries keyed by the configured header row."""
    response = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab}'!A1:ZZ",
    ).execute()
    values = response.get("values", [])
    if not values:
        return []
    headers = values[0]
    return [
        {header: row[index] if index < len(row) else ""
         for index, header in enumerate(headers)}
        for row in values[1:]
        if any(str(value).strip() for value in row)
    ]


def list_people(spreadsheet_url: str, include_archived: bool = False) -> list[dict]:
    """Return the People directory. Legacy rows without is_active are active."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    try:
        people = _read_table(_sheets_service(), spreadsheet_id, "People")
    except Exception as exc:
        if isinstance(exc, GoogleSheetsSetupError):
            raise
        raise _translate_api_error(exc) from exc

    normalised = []
    for person in people:
        active_value = str(person.get("is_active", "TRUE")).strip().casefold()
        person["is_active"] = active_value not in {"false", "0", "no"}
        if include_archived or person["is_active"]:
            normalised.append(person)
    return sorted(
        normalised,
        key=lambda person: (
            str(person.get("display_name", "")).casefold(),
            str(person.get("person_id", "")),
        ),
    )


def add_person(spreadsheet_url: str, display_name: str) -> dict:
    """Add a reusable person, rejecting duplicate active display names."""
    name = display_name.strip()
    if not name:
        raise ValueError("Enter a display name.")
    person = {
        "person_id": str(uuid4()),
        "display_name": name,
        "created_at": _now(),
        "updated_at": _now(),
        "is_active": True,
    }
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    row = [[person[column] for column in SHEET_SCHEMA["People"]]]
    try:
        _sheets_service().spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range="'People'!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"majorDimension": "ROWS", "values": row},
        ).execute()
    except Exception as exc:
        raise _translate_api_error(exc) from exc
    return person


def _find_person_row(service, spreadsheet_id: str, person_id: str) -> int:
    """Find the physical sheet row for a person ID, including archived rows."""
    response = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="'People'!A2:A",
    ).execute()
    for offset, row in enumerate(response.get("values", []), start=2):
        if row and row[0] == person_id:
            return offset
    raise ValueError("That person no longer exists in the People directory.")


def update_person_name(spreadsheet_url: str, person_id: str, display_name: str) -> None:
    """Rename a person without changing their permanent ID."""
    name = display_name.strip()
    if not name:
        raise ValueError("Display name cannot be empty.")
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    try:
        service = _sheets_service()
        row = _find_person_row(service, spreadsheet_id, person_id)
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "RAW",
                "data": [
                    {"range": f"'People'!B{row}", "values": [[name]]},
                    {"range": f"'People'!D{row}", "values":[[_now()]]},
                ],
            },
        ).execute()
    except ValueError:
        raise
    except Exception as exc:
        raise _translate_api_error(exc) from exc


def archive_person(spreadsheet_url: str, person_id: str) -> None:
    """Archive a person; never delete a person referenced by history."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    try:
        service = _sheets_service()
        row = _find_person_row(service, spreadsheet_id, person_id)
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "RAW",
                "data": [
                    {"range": f"'People'!D{row}", "values":[[_now()]]},
                    {"range": f"'People'!E{row}", "values":[[False]]},
                ],
            },
        ).execute()
    except ValueError:
        raise
    except Exception as exc:
        raise _translate_api_error(exc) from exc


def _equal_shares(price: Decimal, people: list[str]) -> dict[str, Decimal]:
    """Reproduce the calculator's deterministic equal-cent split."""
    cents = int(price.quantize(CENT) * 100)
    quotient, remainder = divmod(cents, len(people))
    return {
        person: Decimal(quotient + (1 if index < remainder else 0)) / 100
        for index, person in enumerate(people)
    }


def build_expense_bundle(draft: dict, result) -> dict:
    """Build a stable, retryable set of rows for one calculated expense."""
    expense_id = str(uuid4())
    created_at = _now()
    participants = list(draft["participants"])
    person_ids = draft.get("participant_id_by_name", {})
    if any(person not in person_ids for person in participants):
        raise ValueError(
            "One or more participants are not linked to the People directory. "
            "Return to Bill setup and select them again."
        )

    participant_ids = {person: str(uuid4()) for person in participants}
    billing_mode = draft.get("billing_mode", "GST + service charge")
    nett = billing_mode == "Nett"
    gst_enabled = billing_mode in {"GST + service charge", "GST only"}
    service_enabled = billing_mode in {"GST + service charge", "Service charge only"}

    expense_row = {
        "expense_id": expense_id,
        "expense_name": draft.get("expense_name", "").strip() or "Expense",
        "expense_date": draft["expense_date"].isoformat(),
        "currency": "SGD",
        "receipt_total": str(result.receipt_total) if result.receipt_total is not None else "",
        "subtotal": str(result.subtotal),
        "gst_enabled": gst_enabled,
        "gst_rate": "0.09" if gst_enabled else "0",
        "gst_amount": str(result.gst),
        "service_charge_enabled": service_enabled,
        "service_charge_rate": "0.10" if service_enabled else "0",
        "service_charge_amount": str(result.service_charge),
        "prices_are_nett": nett,
        "calculated_total": str(result.calculated_total),
        "difference": str(result.difference) if result.difference is not None else "",
        "reconciled": result.reconciled if result.reconciled is not None else "",
        "created_at": created_at,
        "calculation_version": CALCULATION_VERSION,
    }

    participant_rows = []
    for index, person in enumerate(participants):
        participant_rows.append({
            "participant_id": participant_ids[person],
            "expense_id": expense_id,
            "person_id": person_ids[person],
            "name_snapshot": person,
            "sort_order": index,
        })

    item_rows = []
    allocation_rows = []
    for item_index, draft_item in enumerate(draft["items"]):
        item_id = str(uuid4())
        item_name = str(draft_item["name"]).strip()
        price = Decimal(str(draft_item["price"])).quantize(CENT)
        assigned_names = list(draft_item["participants"])
        original_shares = _equal_shares(price, assigned_names)

        item_rows.append({
            "item_id": item_id,
            "expense_id": expense_id,
            "item_name": item_name,
            "original_price": str(price),
            "sort_order": item_index,
        })

        allocation = result.item_allocations[item_index]
        for person in assigned_names:
            allocation_rows.append({
                "allocation_id": str(uuid4()),
                "expense_id": expense_id,
                "item_id": item_id,
                "participant_id": participant_ids[person],
                "original_share": str(original_shares[person]),
                "final_share": str(allocation.per_person[person]),
            })

    return {
        "expense_id": expense_id,
        "Expenses": [expense_row],
        "Participants": participant_rows,
        "Items": item_rows,
        "Allocations": allocation_rows,
    }


def _append_missing_rows(
    service,
    spreadsheet_id: str,
    tab: str,
    rows: list[dict],
    id_column: str,
) -> int:
    """Append only IDs not already present, making retries idempotent."""
    if not rows:
        return 0
    id_col_index = SHEET_SCHEMA[tab].index(id_column)
    column_letter = chr(ord("A") + id_col_index)
    existing_values = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab}'!{column_letter}2:{column_letter}",
    ).execute().get("values", [])
    existing_ids = {row[0] for row in existing_values if row and row[0]}

    new_rows = [
        [row.get(column, "") for column in SHEET_SCHEMA[tab]]
        for row in rows
        if row[id_column] not in existing_ids
    ]
    if not new_rows:
        return 0

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab}'!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"majorDimension": "ROWS", "values": new_rows},
    ).execute()
    return len(new_rows)


def save_expense_bundle(spreadsheet_url: str, bundle: dict) -> dict:
    """Append missing rows in dependency order; safe to retry using same bundle IDs.

    Google Sheets does not provide a transaction across tabs. If a call fails
    partway through, re-submit this exact bundle: already written IDs are skipped.
    """
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    try:
        service = _sheets_service()
        counts = {}
        for tab, id_column in (
            ("Expenses", "expense_id"),
            ("Participants", "participant_id"),
            ("Items", "item_id"),
            ("Allocations", "allocation_id"),
        ):
            counts[tab] = _append_missing_rows(
                service, spreadsheet_id, tab, bundle.get(tab, []), id_column
            )
    except Exception as exc:
        if isinstance(exc, (GoogleSheetsSetupError, ValueError)):
            raise
        raise _translate_api_error(exc) from exc
    return {"expense_id": bundle["expense_id"], "inserted": counts}



def restore_person(spreadsheet_url: str, person_id: str) -> None:
    """Restore an archived person without changing their permanent ID."""
    people = list_people(spreadsheet_url, include_archived=True)
    target = next(
        (person for person in people if person["person_id"] == person_id),
        None,
    )
    if target is None:
        raise ValueError("That person no longer exists in the People directory.")
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    try:
        service = _sheets_service()
        row = _find_person_row(service, spreadsheet_id, person_id)
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "RAW",
                "data": [
                    {"range": f"'People'!D{row}", "values":[[_now()]]},
                    {"range": f"'People'!E{row}", "values":[[True]]},
                ],
            },
        ).execute()
    except ValueError:
        raise
    except Exception as exc:
        raise _translate_api_error(exc) from exc
