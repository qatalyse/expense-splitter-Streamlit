# Expense Splitter — Streamlit

Python-first, mobile-friendly expense splitter with a three-step workflow and a UI-independent calculation engine.

## Requirements

- Python 3.10+
- Git

## Setup (Ubuntu / Linux)

```bash
git clone https://github.com/qatalyse/expense-splitter-Streamlit.git
cd expense-splitter-Streamlit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run and test

```bash
python -m unittest discover -s tests
streamlit run app.py
```

Open the local URL shown by Streamlit (usually http://localhost:8501). For phone testing on the same Wi-Fi, run `streamlit run app.py --server.address 0.0.0.0` and open the computer's LAN IP and port from the phone. Do not expose the development server directly to the internet.

## Workflow

1. **Bill setup:** enter comma-separated participant names, optional receipt total, billing mode, and initial item count (default **3**).
2. **Enter items:** item rows start at the requested count. Use **Add another item** or the per-item **✕** button to add/remove rows instantly. Assign people with multiselect (no retyping). **Calculate** moves to results.
3. **Results:** review per-person totals, GST, service charge, and receipt checksum. **Edit items** goes back without losing the draft. **Save to database** is deliberately disabled until persistence is implemented.

**Start over / Reset** requires confirmation. Drafts live in Streamlit session state and are not persistent across session loss, server restart, or browser session expiration. Returning to setup preserves existing items; changing the initial item count after item entry does not overwrite the draft. Use add/remove controls to change its size.

## Where to modify things

- `app.py`: thin entry point, step routing, reset confirmation.
- `ui/setup.py`: setup page.
- `ui/items.py`: dynamic rows, participant selection, Calculate action.
- `ui/results.py`: result presentation and future Save action.
- `ui/state.py`: session-state draft, navigation data, stable item IDs.
- `expense_splitter/models.py`: bill/item/result domain models.
- `expense_splitter/calculator.py`: calculation, GST, service charge, rounding, allocation.
- `expense_splitter/reconciliation.py`: receipt-total checksum.
- `tests/`: automated tests.

The UI builds a `Bill`, calls `split_expense(bill)`, and renders `SplitResult`. Keep business rules out of the UI modules.

## MVP assumptions and deferred work

GST defaults to 9%; service charge to 10%. Service charge applies to the subtotal, and GST applies to subtotal plus service charge. Nett means the entered prices are final. The receipt total is an optional checksum; discrepancies are not silently allocated. Money uses `Decimal`.

Database saving, history, vouchers, discounts, and advanced POS rounding are **not yet implemented**. This is an educational prototype, not tax advice.
