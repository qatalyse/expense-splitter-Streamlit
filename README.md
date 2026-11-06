# Expense Splitter — Streamlit

A Python-first, mobile-accessible expense splitter. The bill creation workflow remains three Streamlit pages; a landing page and expense history pages provide entry points for new and saved expenses. The calculation engine remains independent from the UI and persistence layer.

## Requirements
- Python 3.10+
- Git

## Setup
Clone the repository and enter its directory:

    git clone https://github.com/qatalyse/expense-splitter-Streamlit.git
    cd expense-splitter-Streamlit

Create and activate a virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate

On Windows PowerShell, activate with:

    .venv\Scripts\Activate.ps1

Install dependencies:

    python -m pip install -r requirements.txt

## Run and test

    python -m unittest discover -s tests
    streamlit run app.py

Streamlit prints a local URL. To try the application on a phone on the same Wi-Fi, start the server with:

    streamlit run app.py --server.address 0.0.0.0

Then open the computer's LAN IP and Streamlit port on the phone. Firewall/network settings may need adjustment. Do not expose a development server directly to the public internet.

## Google Sheets connection

The Home page includes the Google Sheets URL field, **Test connection**, and **Initialize database** controls below the two main workflow buttons.

### Local credentials

1. Enable the Google Sheets API in a Google Cloud project.
2. Create a service account and download its JSON key.
3. Share the target spreadsheet with the service-account email as **Editor**.
4. Keep the JSON key in the repository root as `expense-splitter-service.json`. This filename is excluded by `.gitignore`.

Optionally create `.streamlit/secrets.toml` to store the spreadsheet URL and local key path:

    [google_sheets]
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit"
    credentials_file = "expense-splitter-service.json"

The application can also use a root-level `expense-splitter-service.json` without a secrets file. For Streamlit Community Cloud, put the service-account JSON fields under `[gcp_service_account]` in the app's Secrets settings; do not upload the JSON key to GitHub.

### Test and initialize

- **Test connection** performs a read-only metadata request. It confirms the credentials can open the spreadsheet but does not modify it.
- **Initialize database** requires a successful test for the current URL. It creates any missing tabs and writes the expected header row.
- The five tabs are `People`, `Expenses`, `Participants`, `Items`, and `Allocations`. The `People` directory includes an `is_active` flag for archiving. The `Expenses` tab includes `updated_at`, `revision`, `is_archived`, and `archived_at` columns for in-place edits, stale-edit checks, and reversible deletion.
- `People` is an independent master directory of reusable identities (`person_id`, `display_name`, timestamps); it is not a child of `Expenses`.
- `Participants` links a person to one expense using `person_id` and keeps a `name_snapshot` for historical display. `Allocations` references the expense-specific `participant_id` and item ID.
- The People manager is on Page 1. Person IDs are permanent; renaming updates the directory but does not rewrite historical name snapshots. Archiving hides a person from future selection but keeps their record; archived people can be restored.
- Existing non-empty tabs must have exactly the expected headers. If headers differ, initialization stops rather than overwriting or deleting existing data.
- The previous four-tab `Participants` header can be upgraded automatically only when the tab has no data rows. If it already contains records, initialization stops and asks for a deliberate migration; it does not guess person identities.
- Initialization is safe to repeat. It rewrites only the expected header rows and never clears or rewrites records below row 1. It also performs a batched header write to verify write permission.

The spreadsheet URL is kept in the current Streamlit session and copied into the bill draft. To make it available after a fresh session, configure it in `[google_sheets].spreadsheet_url` in Streamlit secrets. New saves use stable UUIDs for each row. If a multi-tab create is interrupted, retrying the same save skips IDs already written and appends only missing rows. Google Sheets does not provide a transaction across tabs, so the UI reports failures and preserves the retry bundle.

### Expense history and editing

- The Home page offers **New expense** and **Expense history**.
- Expense history initially loads the latest 25 summary rows. **Load 25 older expenses** retrieves the next page. Searching by name or filtering by exact date scans only the `Expenses` summary tab; item, participant and allocation details are not loaded for the list.
- Opening one expense loads its matching detail records from `Participants`, `Items`, and `Allocations`.
- The history list hides archived expenses by default. **Show archived expenses** reveals them, and the detail page offers Restore.
- **Duplicate** creates a new unsaved draft from the selected expense, with a fresh expense ID and new item/participant/allocation IDs when saved. The source expense is unchanged.
- **Delete expense** is a reversible soft delete: it sets `is_archived` and `archived_at`; it does not physically remove the expense or its child rows.
- Historical breakdowns use stored `final_share` values and the shared `presentation/expense_breakdown.py` renderer. They are not recalculated, so the original copyable monospace WhatsApp breakdown is preserved.
- Editing loads the saved data into the existing three-page workflow. Saving updates the original `expense_id`, keeps `created_at`, increments `revision`, and updates `updated_at`.
- Child rows are replaced in one Google Sheets `spreadsheets.batchUpdate` request, preserving unchanged participant, item and allocation IDs. A revision check rejects edits opened before a newer saved revision. This is an optimistic stale-edit check, not a database-level lock.
- After merging this change, open Bill setup and click **Initialize database** once to add `updated_at` and `revision` to the existing `Expenses` tab. Existing expense rows are retained; `updated_at` is initialized from `created_at` and `revision` to `1`.

## Application pages
- **Home:** choose New expense or Expense history; configure and initialize the Google Sheets connection below these two actions.
- **Expense history:** browse, search, date-filter, view, edit or duplicate saved expenses; optionally show archived expenses.
- **Saved expense:** view the original item matrix and copyable monospace breakdown, edit or duplicate it, and delete/restore it through reversible archiving.
- **Page 1 — Bill setup:** expense name, expense date (defaults to Singapore's current date), optional receipt total, billing mode, initial number of item rows (default 3), and reusable People management (select, add, rename, archive and restore people).
- **Page 2 — Item entry:** item names, prices and participant assignments. Add or remove item rows dynamically.
- **Page 3 — Results:** shared charge-inclusive item/person allocation matrix, copyable WhatsApp breakdowns, receipt reconciliation, and create/update persistence to Google Sheets.

The in-progress bill is held in Streamlit session state while the user navigates between pages.

## Where to change things
- **Navigation:** app.py
- **Reusable replaceable status messages:** ui/status.py
- **Page UI:** pages/1_Bill_Setup.py, pages/2_Item_Entry.py, pages/3_Results.py
- **Shared page state and input conversion:** pages/common.py
- **Google Sheets schema and connection setup:** database/google_sheets.py
- **Google Sheets People and expense persistence:** database/sheets_repository.py
- **Reusable breakdown presentation:** presentation/expense_breakdown.py
- **Expense history and saved expense view:** pages/4_Expense_History.py, pages/5_Expense_Detail.py
- **WhatsApp share formatting:** presentation/share_format.py
- **Domain data structures:** expense_splitter/models.py
- **Calculations and item/person allocation:** expense_splitter/calculator.py
- **Receipt checksum:** expense_splitter/reconciliation.py
- **Tests:** tests/

Keep GST, service charge, allocation and reconciliation rules in expense_splitter/, not in the page scripts. The UI should construct a Bill, call split_expense(bill), and display the returned SplitResult.

## MVP assumptions
- GST defaults to 9%; service charge defaults to 10%.
- Service charge applies to subtotal; GST applies to subtotal plus service charge.
- Nett mode treats entered item prices as final and adds no extra charges.
- Shared item prices are divided in cents; remainder cents are allocated deterministically.
- GST and service charge are distributed across item/person cells, so item-level displayed amounts include applicable charges and add up exactly to the calculated total.
- Receipt total is optional. Differences over SGD 0.01 are reported, not silently distributed.
- Money calculations use Decimal.

This is an educational prototype, not tax advice. Permanent destruction of archived records, full audit history, establishment-specific nett treatment and advanced POS rounding remain out of scope.
