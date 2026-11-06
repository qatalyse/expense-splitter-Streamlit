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
    """Return the People directory after verifying the current People schema."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    try:
        service = _sheets_service()
        header_response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="'People'!1:1",
        ).execute()
        actual_headers = (
            header_response.get("values", [[]])[0]
            if header_response.get("values") else []
        )
        if actual_headers != list(SHEET_SCHEMA["People"]):
            raise GoogleSheetsSetupError(
                "The People tab needs the latest schema. Click Initialize database "
                "on Page 1 to add or validate the is_active column before managing people."
            )
        people = _read_table(service, spreadsheet_id, "People")
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
        "updated_at": created_at,
        "revision": "1",
        "is_archived": False,
        "archived_at": "",
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
        _assert_expense_schema(service, spreadsheet_id)
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



def _read_rows_with_numbers(service, spreadsheet_id: str, tab: str) -> list[dict]:
    """Read records with their current 1-based physical row numbers."""
    response = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab}'!A1:ZZ",
    ).execute()
    values = response.get("values", [])
    if not values:
        return []
    headers = values[0]
    records = []
    for row_number, values_row in enumerate(values[1:], start=2):
        if not any(str(value).strip() for value in values_row):
            continue
        record = {
            header: values_row[index] if index < len(values_row) else ""
            for index, header in enumerate(headers)
        }
        record["_row_number"] = row_number
        records.append(record)
    return records


def _assert_expense_schema(service, spreadsheet_id: str) -> None:
    """Require the migrated expense schema before browsing or modifying history."""
    response = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="'Expenses'!1:1",
    ).execute()
    headers = response.get("values", [[]])[0] if response.get("values") else []
    if headers != list(SHEET_SCHEMA["Expenses"]):
        raise GoogleSheetsSetupError(
            "The Expenses tab needs the latest schema for history and editing. "
            "Open Bill setup and click Initialize database before continuing."
        )


def list_expense_summaries(
    spreadsheet_url: str,
    page: int = 0,
    page_size: int = 25,
    search: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    include_archived: bool = False,
) -> dict:
    """Return a page of expense summaries without loading detail tabs.

    The normal path reads only IDs for pagination and requests the selected
    summary rows. Searching or date filtering scans only the Expenses summary
    tab; item, participant and allocation tabs are never loaded here.
    """
    if page < 0 or page_size < 1 or page_size > 100:
        raise ValueError("Invalid expense-history page size or page number.")

    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    try:
        service = _sheets_service()
        _assert_expense_schema(service, spreadsheet_id)
        search_text = search.strip().casefold()
        if search_text or date_from or date_to:
            all_rows = _read_rows_with_numbers(service, spreadsheet_id, "Expenses")
            candidates = [
                row for row in all_rows
                if (include_archived or str(row.get("is_archived", "FALSE")).casefold() not in {"true", "1", "yes"})
                and (not search_text or search_text in str(row.get("expense_name", "")).casefold())
                and (not date_from or str(row.get("expense_date", "")) >= date_from)
                and (not date_to or str(row.get("expense_date", "")) <= date_to)
            ]
            candidates.sort(
                key=lambda row: (
                    str(row.get("created_at", "")),
                    str(row.get("expense_date", "")),
                ),
                reverse=True,
            )
            total_count = len(candidates)
            start = page * page_size
            selected = candidates[start:start + page_size]
        else:
            ids = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range="'Expenses'!A2:A",
            ).execute().get("values", [])
            archived_flags = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range="'Expenses'!U2:U",
            ).execute().get("values", [])
            populated_row_numbers = []
            for index, row in enumerate(ids):
                if not row or not row[0].strip():
                    continue
                flag_row = archived_flags[index] if index < len(archived_flags) else []
                is_archived = bool(flag_row) and str(flag_row[0]).strip().casefold() in {"true", "1", "yes"}
                if include_archived or not is_archived:
                    populated_row_numbers.append(index + 2)

            total_count = len(populated_row_numbers)
            end = max(total_count - page * page_size, 0)
            start = max(end - page_size, 0)
            chosen_row_numbers = list(reversed(populated_row_numbers[start:end]))
            if chosen_row_numbers:
                ranges = [f"'Expenses'!A{row}:V{row}" for row in chosen_row_numbers]
                response = service.spreadsheets().values().batchGet(
                    spreadsheetId=spreadsheet_id,
                    ranges=ranges,
                ).execute()
                selected = []
                for row_number, value_range in zip(
                    chosen_row_numbers, response.get("valueRanges", [])
                ):
                    values = value_range.get("values", [[]])[0]
                    selected.append({
                        header: values[index] if index < len(values) else ""
                        for index, header in enumerate(SHEET_SCHEMA["Expenses"])
                    } | {"_row_number": row_number})
            else:
                selected = []
    except ValueError:
        raise
    except Exception as exc:
        raise _translate_api_error(exc) from exc

    return {
        "expenses": selected,
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "has_more": (page + 1) * page_size < total_count,
    }


def get_expense_details(spreadsheet_url: str, expense_id: str) -> dict:
    """Load one expense and its related rows on demand."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    try:
        service = _sheets_service()
        _assert_expense_schema(service, spreadsheet_id)
        metadata = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets(properties(sheetId,title))",
        ).execute()
        sheet_ids = {
            sheet["properties"]["title"]: sheet["properties"]["sheetId"]
            for sheet in metadata.get("sheets", [])
        }

        expense_rows = _read_rows_with_numbers(service, spreadsheet_id, "Expenses")
        expense_matches = [
            row for row in expense_rows if row.get("expense_id") == expense_id
        ]
        if len(expense_matches) != 1:
            raise ValueError("The selected expense could not be found uniquely.")
        expense = expense_matches[0]

        related = {}
        for tab in ("Participants", "Items", "Allocations"):
            related[tab] = [
                row for row in _read_rows_with_numbers(service, spreadsheet_id, tab)
                if row.get("expense_id") == expense_id
            ]

        related["Participants"].sort(key=lambda row: int(row.get("sort_order") or 0))
        related["Items"].sort(key=lambda row: int(row.get("sort_order") or 0))
        return {
            "expense": expense,
            "Participants": related["Participants"],
            "Items": related["Items"],
            "Allocations": related["Allocations"],
            "sheet_ids": sheet_ids,
        }
    except ValueError:
        raise
    except Exception as exc:
        raise _translate_api_error(exc) from exc


def historical_result_from_details(details: dict):
    """Reconstruct the saved breakdown for display without recalculating it."""
    from datetime import date
    from expense_splitter.models import ItemAllocation, SplitResult

    participants = {
        row["participant_id"]: row.get("name_snapshot", "")
        for row in details["Participants"]
    }
    allocations_by_item: dict[str, dict[str, Decimal]] = {}
    for row in details["Allocations"]:
        person_name = participants.get(row.get("participant_id"))
        if person_name is None:
            continue
        allocations_by_item.setdefault(row.get("item_id", ""), {})[person_name] = Decimal(
            row.get("final_share") or "0"
        )

    item_allocations = []
    for item in details["Items"]:
        per_person = allocations_by_item.get(item["item_id"], {})
        item_total = sum(per_person.values(), Decimal("0.00"))
        item_allocations.append(
            ItemAllocation(
                item_name=item.get("item_name", ""),
                per_person=per_person,
                total=item_total,
            )
        )

    expense = details["expense"]
    per_person: dict[str, Decimal] = {}
    for allocation in item_allocations:
        for person, amount in allocation.per_person.items():
            per_person[person] = per_person.get(person, Decimal("0.00")) + amount

    receipt = expense.get("receipt_total")
    difference = expense.get("difference")
    reconciled = expense.get("reconciled")
    subtotal = Decimal(expense.get("subtotal") or "0")
    service_charge = Decimal(expense.get("service_charge_amount") or "0")
    gst = Decimal(expense.get("gst_amount") or "0")
    calculated_total = Decimal(expense.get("calculated_total") or "0")

    result = SplitResult(
        subtotal=subtotal,
        service_charge=service_charge,
        gst=gst,
        calculated_total=calculated_total,
        receipt_total=Decimal(receipt) if receipt else None,
        difference=Decimal(difference) if difference else None,
        reconciled=(
            reconciled.strip().casefold() in {"true", "1", "yes"}
            if reconciled != "" else None
        ),
        per_person=per_person,
        item_allocations=item_allocations,
    )
    return result


def draft_from_expense_details(details: dict, spreadsheet_url: str) -> dict:
    """Convert a saved expense into the existing three-page editing draft."""
    from datetime import date
    from uuid import uuid4

    expense = details["expense"]
    participant_by_id = {
        row["participant_id"]: row for row in details["Participants"]
    }
    names = [
        row.get("name_snapshot", "")
        for row in details["Participants"]
    ]
    person_id_by_name = {
        row.get("name_snapshot", ""): row.get("person_id", "")
        for row in details["Participants"]
    }
    allocations_by_item: dict[str, list[str]] = {}
    for allocation in details["Allocations"]:
        participant = participant_by_id.get(allocation.get("participant_id"))
        if participant:
            allocations_by_item.setdefault(allocation.get("item_id", ""), []).append(
                participant.get("name_snapshot", "")
            )

    items = [
        {
            "id": str(uuid4()),
            "item_id": row["item_id"],
            "name": row.get("item_name", ""),
            "price": row.get("original_price", ""),
            "participants": allocations_by_item.get(row["item_id"], []),
        }
        for row in details["Items"]
    ]

    gst_enabled = str(expense.get("gst_enabled", "")).casefold() in {"true", "1", "yes"}
    service_enabled = str(expense.get("service_charge_enabled", "")).casefold() in {"true", "1", "yes"}
    if str(expense.get("prices_are_nett", "")).casefold() in {"true", "1", "yes"}:
        billing_mode = "Nett"
    elif gst_enabled and service_enabled:
        billing_mode = "GST + service charge"
    elif gst_enabled:
        billing_mode = "GST only"
    elif service_enabled:
        billing_mode = "Service charge only"
    else:
        billing_mode = "Nett"

    expense_date = date.fromisoformat(expense["expense_date"])
    return {
        "expense_name": expense.get("expense_name", ""),
        "expense_date": expense_date,
        "participants": names,
        "participant_id_by_name": person_id_by_name,
        "participant_ids": [row.get("person_id", "") for row in details["Participants"]],
        "receipt_total": expense.get("receipt_total", ""),
        "billing_mode": billing_mode,
        "initial_item_count": max(1, len(items)),
        "items": items,
        "spreadsheet_url": spreadsheet_url,
        "editing_expense_id": expense["expense_id"],
        "editing_created_at": expense.get("created_at", ""),
        "editing_revision": int(expense.get("revision") or "1"),
        "editing_original_details": details,
    }


def _cell_data(value) -> dict:
    """Convert a value to a Sheets CellData userEnteredValue."""
    if isinstance(value, bool):
        return {"userEnteredValue": {"boolValue": value}}
    if value is None or value == "":
        return {"userEnteredValue": {}}
    return {"userEnteredValue": {"stringValue": str(value)}}


def _row_data(tab: str, row: dict) -> dict:
    return {
        "values": [
            _cell_data(row.get(column, ""))
            for column in SHEET_SCHEMA[tab]
        ]
    }


def update_expense_bundle(
    spreadsheet_url: str,
    bundle: dict,
    expected_revision: int,
) -> dict:
    """Replace an expense and its child rows in one Sheets batchUpdate request.

    Uses the stable expense_id and checks the current revision before writing.
    Related rows are deleted by their recorded row positions, then replacement
    rows are appended in the same atomic spreadsheets.batchUpdate call.
    """
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    details = get_expense_details(spreadsheet_url, bundle["expense_id"])
    current_revision = int(details["expense"].get("revision") or "1")
    target_expense = bundle["Expenses"][0]
    # A client may time out after Google has atomically accepted the update.
    # Recognise that exact already-applied revision as a successful retry.
    if (
        current_revision == expected_revision + 1
        and details["expense"].get("updated_at") == target_expense.get("updated_at")
    ):
        return {
            "expense_id": bundle["expense_id"],
            "revision": current_revision,
            "updated": True,
            "already_applied": True,
        }
    if current_revision != expected_revision:
        raise GoogleSheetsSetupError(
            "This expense was modified after you opened it. Reload it from Expense "
            "History before saving, so you do not overwrite newer changes."
        )

    service = _sheets_service()
    requests = []
    sheet_ids = details["sheet_ids"]

    for tab in ("Participants", "Items", "Allocations"):
        rows = details[tab]
        for row in sorted(rows, key=lambda item: item["_row_number"], reverse=True):
            row_index = row["_row_number"] - 1
            requests.append({
                "deleteDimension": {
                    "range": {
                        "sheetId": sheet_ids[tab],
                        "dimension": "ROWS",
                        "startIndex": row_index,
                        "endIndex": row_index + 1,
                    }
                }
            })

    expense = bundle["Expenses"][0]
    expense_row_index = details["expense"]["_row_number"] - 1
    requests.append({
        "updateCells": {
            "start": {
                "sheetId": sheet_ids["Expenses"],
                "rowIndex": expense_row_index,
                "columnIndex": 0,
            },
            "rows": [_row_data("Expenses", expense)],
            "fields": "userEnteredValue",
        }
    })

    for tab in ("Participants", "Items", "Allocations"):
        rows = bundle.get(tab, [])
        if rows:
            requests.append({
                "appendCells": {
                    "sheetId": sheet_ids[tab],
                    "rows": [_row_data(tab, row) for row in rows],
                    "fields": "userEnteredValue",
                }
            })

    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()
    except Exception as exc:
        raise _translate_api_error(exc) from exc

    return {
        "expense_id": bundle["expense_id"],
        "revision": int(expense["revision"]),
        "updated": True,
    }


def build_update_bundle(draft: dict, result, existing_details: dict) -> dict:
    """Build replacement rows while retaining IDs for unchanged records."""
    bundle = build_expense_bundle(draft, result)
    expense_id = draft["editing_expense_id"]
    existing_expense = existing_details["expense"]
    bundle["expense_id"] = expense_id

    old_participants = {
        row.get("person_id"): row
        for row in existing_details["Participants"]
    }
    new_participant_ids = {}
    for row in bundle["Participants"]:
        generated_id = row["participant_id"]
        previous = old_participants.get(row["person_id"])
        if previous:
            row["participant_id"] = previous["participant_id"]
        new_participant_ids[generated_id] = row["participant_id"]
        row["expense_id"] = expense_id

    new_item_ids = {}
    old_items = {
        row.get("item_id"): row
        for row in existing_details["Items"]
    }
    for index, row in enumerate(bundle["Items"]):
        generated_id = row["item_id"]
        draft_item = draft["items"][index]
        previous = old_items.get(draft_item.get("item_id"))
        if previous:
            row["item_id"] = previous["item_id"]
        new_item_ids[generated_id] = row["item_id"]
        row["expense_id"] = expense_id

    old_allocations = {
        (row.get("item_id"), row.get("participant_id")): row.get("allocation_id")
        for row in existing_details["Allocations"]
    }
    for row in bundle["Allocations"]:
        generated_item_id = row["item_id"]
        generated_participant_id = row["participant_id"]
        row["item_id"] = new_item_ids[generated_item_id]
        row["participant_id"] = new_participant_ids[generated_participant_id]
        row["expense_id"] = expense_id
        previous_allocation_id = old_allocations.get(
            (row["item_id"], row["participant_id"])
        )
        if previous_allocation_id:
            row["allocation_id"] = previous_allocation_id

    expense = bundle["Expenses"][0]
    expense["expense_id"] = expense_id
    expense["created_at"] = existing_expense.get("created_at", expense["created_at"])
    expense["updated_at"] = _now()
    expense["revision"] = str(int(existing_expense.get("revision") or "1") + 1)
    return bundle



def set_expense_archived(spreadsheet_url: str, expense_id: str, archived: bool,
                         expected_revision: int | None = None) -> dict:
    """Soft-delete or restore an expense without deleting its child rows."""
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    details = get_expense_details(spreadsheet_url, expense_id)
    expense = details["expense"]
    revision = int(expense.get("revision") or "1")
    if expected_revision is not None and expected_revision != revision:
        raise GoogleSheetsSetupError(
            "This expense changed since it was opened. Reload it before trying again."
        )
    current_archived = str(expense.get("is_archived", "FALSE")).casefold() in {"true", "1", "yes"}
    if current_archived == archived:
        return {"expense_id": expense_id, "archived": archived, "unchanged": True}

    now = _now()
    service = _sheets_service()
    try:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "RAW",
                "data": [
                    {"range": f"'Expenses'!S{expense['_row_number']}", "values": [[now]]},
                    {"range": f"'Expenses'!T{expense['_row_number']}", "values": [[str(revision + 1)]]},
                    {"range": f"'Expenses'!U{expense['_row_number']}", "values": [[archived]]},
                    {"range": f"'Expenses'!V{expense['_row_number']}", "values": [[now if archived else ""]]},
                ],
            },
        ).execute()
    except Exception as exc:
        raise _translate_api_error(exc) from exc
    return {"expense_id": expense_id, "archived": archived, "revision": revision + 1}


def duplicate_draft_from_expense_details(details: dict, spreadsheet_url: str) -> dict:
    """Create a new unsaved draft from an existing expense without its identity."""
    draft = draft_from_expense_details(details, spreadsheet_url)
    for key in (
        "editing_expense_id", "editing_created_at", "editing_revision",
        "editing_original_details",
    ):
        draft.pop(key, None)
    source_name = draft.get("expense_name", "").strip() or "Expense"
    draft["expense_name"] = f"Copy of {source_name}"
    for item in draft["items"]:
        item.pop("item_id", None)
    draft["is_duplicate_draft"] = True
    return draft
