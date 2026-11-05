# Expense Splitter

Python-first expense-splitting prototype with a mobile-accessible UI. The calculation core is independent from the frontend.

## Requirements
- Python 3.10+
- Git

## Setup
Clone this repository, enter its directory, create and activate a virtual environment:

    python -m venv .venv
    # macOS/Linux
    source .venv/bin/activate
    # Windows PowerShell
    .venv\Scripts\Activate.ps1

Install dependencies:

    python -m pip install --upgrade pip
    pip install -r requirements.txt

## Run
Streamlit version:

    streamlit run app.py

NiceGUI version:

    python app.py

Open the local URL printed in the terminal. To try it on a phone on the same Wi-Fi, configure the development server to bind to the computer's LAN interface, then open the computer's LAN IP from the phone. Firewall settings may need adjustment. Do not expose a development server directly to the public internet.

## Where to change things
- **UI and interactions:** app.py
- **Data structures:** expense_splitter/models.py
- **Calculations and item allocation:** expense_splitter/calculator.py
- **Receipt checksum:** expense_splitter/reconciliation.py
- **Tests:** tests/test_calculator.py

Keep GST, service charge, rounding and allocation policy out of app.py. The frontend should build a Bill, call split_expense(bill), and display the returned SplitResult.

## MVP assumptions
- Add participants, items and participant assignments for each item.
- Shared items are divided in cents; remainder cents are assigned deterministically.
- GST defaults to 9% and service charge to 10%; both can be toggled independently.
- Service charge applies to subtotal; GST applies to subtotal plus service charge.
- Nett mode treats entered prices as final and adds no extra GST/service charge.
- Receipt total is optional. Differences over SGD 0.01 are reported, not silently distributed.
- Uses Decimal for money.

This is an educational prototype, not tax advice. Discounts, vouchers, establishment-specific nett treatment and advanced POS rounding are out of scope for this MVP.
