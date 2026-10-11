# Expense Splitter — Streamlit

A Python-first, mobile-accessible expense-splitting prototype. The UI is built with Streamlit; bill models and calculation logic live in separate modules so the UI can be replaced later without rewriting the core.

> **Project status:** starter scaffold. The GST/service-charge calculation is a prototype, not tax advice. Check the receipt and relevant rules for the specific business.

## Requirements

- Python 3.10+
- `git` (optional, for cloning)

## Setup

```bash
git clone https://github.com/qatalyse/expense-splitter-Streamlit.git
cd expense-splitter-Streamlit

python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Streamlit prints a local URL. To use the app from a phone on the same Wi-Fi, run it with `streamlit run app.py --server.address 0.0.0.0` and open the computer's LAN IP plus the displayed port on the phone. Firewall/network settings may need adjustment. Do not expose the development server directly to the public internet.

## Where to change things

- **UI and interactions:** `app.py` — form fields, adding people/items, toggles, calculate button, and displaying results.
- **Data structures:** `expense_splitter/models.py` — `Item`, `BillingRules`, `Bill`, and `SplitResult`.
- **Calculation/business rules:** `expense_splitter/calculator.py` — allocation, service charge, GST, per-person shares and calculated total.
- **Checksum / POS total comparison:** `expense_splitter/reconciliation.py` — compares the calculated amount with the optional receipt total; discrepancies are reported, not silently spread among diners.
- **Tests:** `tests/` — run with `python -m unittest discover -s tests`.

The UI should collect inputs and call `split_expense(bill)`. Keep tax, rounding and allocation rules out of `app.py`, which makes a later move to FastAPI + React much easier.

## Current behavior

- Add named participants and items, assigning each item to one or more participants.
- Split a shared item's price evenly between assigned participants.
- Toggle GST (default 9%) and service charge (default 10%) independently.
- Enter an optional receipt total as a checksum.
- Use `Decimal` for money; calculated totals and item-level shares are rounded to cents.

This is an early scaffold: receipt-specific discounts, vouchers, advanced nett-price interpretation and POS-specific rounding policies still need explicit modeling.
