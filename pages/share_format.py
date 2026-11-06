"""Plain-text share-message formatting for WhatsApp and similar chats."""
from datetime import date
from decimal import Decimal

from expense_splitter.models import ItemAllocation


def _format_person_lines(
    person: str,
    item_allocations: list[ItemAllocation],
    total: Decimal,
) -> list[str]:
    """Format one person's rows with dynamically aligned amounts."""
    rows = [
        (allocation.item_name, allocation.per_person[person])
        for allocation in item_allocations
        if person in allocation.per_person
    ]
    if not rows:
        return [person, "", "No assigned items.", "", "TOTAL = $0.00"]

    name_width = max(len("TOTAL"), *(len(name) for name, _ in rows)) + 2
    amounts = ["$" + format(amount, ".2f") for _, amount in rows]
    total_text = "$" + format(total, ".2f")
    amount_width = max(len(total_text), *(len(value) for value in amounts)) + 1
    line_width = name_width + amount_width

    lines = [person, ""]
    for (name, _), amount_text in zip(rows, amounts):
        lines.append(f"{name:<{name_width}}{amount_text:>{amount_width}}")
    lines.append("-" * line_width)
    lines.append(f"{'TOTAL':<{name_width}}{total_text:>{amount_width}}")
    return lines


def format_person_message(
    expense_name: str,
    expense_date: date,
    person: str,
    item_allocations: list[ItemAllocation],
    total: Decimal,
) -> str:
    """Format one WhatsApp monospace message, including expense context."""
    title = expense_name.strip() or "Expense"
    header = f"{title} {expense_date:%d/%m/%Y}"
    lines = [header, "", "```", *_format_person_lines(person, item_allocations, total), "```"]
    return "\n".join(lines)


def format_all_message(
    expense_name: str,
    expense_date: date,
    people: dict[str, Decimal],
    item_allocations: list[ItemAllocation],
    grand_total: Decimal,
) -> str:
    """Format every participant into one WhatsApp-ready message."""
    title = expense_name.strip() or "Expense"
    header = f"{title} {expense_date:%d/%m/%Y}"
    lines = [header, "", "```"]
    for index, (person, total) in enumerate(people.items()):
        if index:
            lines.extend(["", ""])
        lines.extend(_format_person_lines(person, item_allocations, total))
    lines.extend(["", "", "GRAND TOTAL = $" + format(grand_total, ".2f"), "```"])
    return "\n".join(lines)
