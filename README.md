# Expense Splitter — Streamlit

A Python-first, mobile-accessible expense splitter. The UI is organised into three separate Streamlit pages, while the calculation engine remains independent from the UI.

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

Page 1 includes a Google Sheets URL field, **Test connection**, and **Initialize database** controls below the initial item-row count.

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
- The four tabs are `Expenses`, `Participants`, `Items`, and `Allocations`.
- Existing non-empty tabs must have exactly the expected headers. If headers differ, initialization stops rather than overwriting or deleting existing data.
- Initialization is safe to repeat. It does not clear existing rows.

The spreadsheet URL is kept in the current Streamlit session and copied into the bill draft when continuing to Page 2. Database writes of completed expenses are a separate follow-up feature; this change only adds connection testing and schema initialization.

## Application pages
- **Page 1 — Bill setup:** expense name, expense date (defaults to Singapore's current date), participants, optional receipt total, billing mode and initial number of item rows (default 3).
- **Page 2 — Item entry:** item names, prices and participant assignments. Add or remove item rows dynamically.
- **Page 3 — Results:** charge-inclusive item/person allocation matrix, copyable WhatsApp breakdowns, and receipt reconciliation. Database saving remains a disabled placeholder.

The in-progress bill is held in Streamlit session state while the user navigates between pages.

## Where to change things
- **Navigation:** app.py
- **Page UI:** pages/1_Bill_Setup.py, pages/2_Item_Entry.py, pages/3_Results.py
- **Shared page state and input conversion:** pages/common.py
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

This is an educational prototype, not tax advice. Discounts, vouchers, database persistence, establishment-specific nett treatment and advanced POS rounding are out of scope for this update.
