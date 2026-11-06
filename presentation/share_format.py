"""WhatsApp-friendly text formatting for calculated participant shares."""
from datetime import date
from decimal import Decimal

from expense_splitter.models import ItemAllocation

_FENCE = chr(96) * 3


def _person_lines(person: str, item_allocations: list[ItemAllocation], total: Decimal) -> list[str]:
    rows = [
        (row.item_name, row.per_person[person])
        for row in item_allocations
        if person in row.per_person
    ]
    if not rows:
        return [person, "", "No assigned items.", "", "TOTAL = $0.00"]

    name_width = max(len("TOTAL"), *(len(name) for name, _ in rows)) + 2
    amount_texts = ["$" + format(amount, ".2f") for _, amount in rows]
    total_text = "$" + format(total, ".2f")
    amount_width = max(len(total_text), *(len(value) for value in amount_texts)) + 1
    separator_width = name_width + amount_width

    lines = [person, ""]
    for (name, _), amount in zip(rows, amount_texts):
        lines.append(f"{name:<{name_width}}{amount:>{amount_width}}")
    lines.append("-" * separator_width)
    lines.append(f"{'TOTAL':<{name_width}}{total_text:>{amount_width}}")
    return lines


def format_person_message(
    expense_name: str,
    expense_date: date,
    person: str,
    item_allocations: list[ItemAllocation],
    total: Decimal,
) -> str:
    """Return one participant's message with WhatsApp monospace markers."""
    title = expense_name.strip() or "Expense"
    header = f"{title} {expense_date:%d/%m/%Y}"
    return "\n".join([
        _FENCE, header, "",
        *_person_lines(person, item_allocations, total),
        _FENCE,
    ])


def format_all_message(
    expense_name: str,
    expense_date: date,
    people: dict[str, Decimal],
    item_allocations: list[ItemAllocation],
    grand_total: Decimal,
) -> str:
    """Return a single message containing all participants' breakdowns."""
    title = expense_name.strip() or "Expense"
    header = f"{title} {expense_date:%d/%m/%Y}"
    lines = [_FENCE, header, ""]
    for index, (person, total) in enumerate(people.items()):
        if index:
            lines.extend(["", ""])
        lines.extend(_person_lines(person, item_allocations, total))
    lines.extend(["", "", "GRAND TOTAL = $" + format(grand_total, ".2f"), _FENCE])
    return "\n".join(lines)



def format_combined_person_message(person: str, expenses: list[dict]) -> str:
    """Format one person's stored shares across multiple expenses for WhatsApp."""
    if not expenses:
        raise ValueError("Select at least one expense to consolidate.")

    lines = [_FENCE, f"{person} — Combined Expenses", ""]
    grand_total = Decimal("0.00")

    for index, expense in enumerate(expenses):
        if index:
            lines.extend(["", ""])
        raw_date = expense["expense_date"]
        expense_date = (
            raw_date if isinstance(raw_date, date)
            else date.fromisoformat(str(raw_date))
        )
        lines.extend([
            f"{expense.get('expense_name', 'Expense')} {expense_date:%d/%m/%Y}",
            "",
        ])

        rows = [
            (allocation.item_name, allocation.per_person[person])
            for allocation in expense["item_allocations"]
            if person in allocation.per_person
        ]
        subtotal = sum((amount for _, amount in rows), Decimal("0.00"))
        grand_total += subtotal

        if rows:
            name_width = max(
                len("SUBTOTAL"),
                *(len(name) for name, _ in rows),
            ) + 2
            amount_values = ["$" + format(amount, ".2f") for _, amount in rows]
            subtotal_text = "$" + format(subtotal, ".2f")
            amount_width = max(
                len(subtotal_text),
                *(len(value) for value in amount_values),
            ) + 1
            for (item_name, _), amount_text in zip(rows, amount_values):
                lines.append(
                    f"{item_name:<{name_width}}{amount_text:>{amount_width}}"
                )
            lines.append("-" * (name_width + amount_width))
            lines.append(
                f"{'SUBTOTAL':<{name_width}}{subtotal_text:>{amount_width}}"
            )
        else:
            lines.append("No assigned items.")
            lines.append("SUBTOTAL = $0.00")

    lines.extend([
        "",
        "",
        "=" * 32,
        "GRAND TOTAL = $" + format(grand_total, ".2f"),
        _FENCE,
    ])
    return "\n".join(lines)
