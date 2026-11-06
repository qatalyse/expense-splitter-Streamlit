"""UI-independent bill calculation and charge-inclusive item allocation."""
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

from .models import Bill, ItemAllocation, SplitResult
from .reconciliation import reconcile_total

_CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _allocate_amount(
    amount: Decimal,
    weights: dict[tuple[int, str], Decimal],
) -> dict[tuple[int, str], Decimal]:
    """Allocate a charge in cents across item/person cells proportionally.

    Largest-remainder allocation ensures the returned cell amounts sum exactly
    to the requested adjustment. Insertion order gives deterministic tie-breaking.
    """
    if not weights:
        return {}
    weight_total = sum(weights.values(), Decimal("0"))
    if weight_total <= 0:
        return {key: Decimal("0.00") for key in weights}

    cents = int(_money(amount) * 100)
    exact = {
        key: Decimal(cents) * weight / weight_total
        for key, weight in weights.items()
    }
    allocated = {
        key: int(value.to_integral_value(rounding=ROUND_FLOOR))
        for key, value in exact.items()
    }
    remaining = cents - sum(allocated.values())
    ranked = sorted(
        exact,
        key=lambda key: exact[key] - allocated[key],
        reverse=True,
    )
    for key in ranked[:remaining]:
        allocated[key] += 1
    return {key: Decimal(value) / 100 for key, value in allocated.items()}


def split_expense(bill: Bill) -> SplitResult:
    """Calculate bill totals and final per-item/per-person allocations.

    MVP assumptions:
    - Service charge applies to subtotal.
    - GST applies to subtotal plus service charge.
    - Nett mode treats item prices as final and adds no extra charges.
    - Charges are allocated proportionally across item/person cells.
    - Receipt total is a checksum; differences are never silently distributed.
    """
    if not bill.items:
        raise ValueError("Add at least one item.")

    base_cells: dict[tuple[int, str], Decimal] = {}
    subtotal = Decimal("0.00")

    for item_index, item in enumerate(bill.items):
        if not item.name.strip():
            raise ValueError("Every item needs a name.")
        price = _money(item.price)
        if price < 0:
            raise ValueError(f"Item {item.name!r} cannot have a negative price.")

        participants = list(dict.fromkeys(
            person.strip() for person in item.participants if person.strip()
        ))
        if not participants:
            raise ValueError(f"Assign at least one participant to {item.name!r}.")

        subtotal += price
        quotient, remainder = divmod(int(price * 100), len(participants))
        for index, person in enumerate(participants):
            cents = quotient + (1 if index < remainder else 0)
            base_cells[(item_index, person)] = Decimal(cents) / 100

    subtotal = _money(subtotal)
    rules = bill.billing

    if rules.prices_are_nett:
        service_charge = Decimal("0.00")
        gst = Decimal("0.00")
    else:
        service_charge = (
            _money(subtotal * rules.service_charge_rate)
            if rules.service_charge_enabled else Decimal("0.00")
        )
        taxable_amount = subtotal + service_charge
        gst = (
            _money(taxable_amount * rules.gst_rate)
            if rules.gst_enabled else Decimal("0.00")
        )

    calculated_total = _money(subtotal + service_charge + gst)

    # Allocate each adjustment to item/person cells so the result can show
    # each person's final cost for each item, with charges already included.
    final_cells = dict(base_cells)
    for adjustment in (service_charge, gst):
        if adjustment:
            charge_cells = _allocate_amount(adjustment, base_cells)
            final_cells = {
                key: value + charge_cells.get(key, Decimal("0.00"))
                for key, value in final_cells.items()
            }

    item_allocations: list[ItemAllocation] = []
    per_person: dict[str, Decimal] = {}
    for item_index, item in enumerate(bill.items):
        allocated_to_item = {
            person: amount
            for (cell_item_index, person), amount in final_cells.items()
            if cell_item_index == item_index
        }
        item_total = _money(sum(allocated_to_item.values(), Decimal("0.00")))
        item_allocations.append(ItemAllocation(
            item_name=item.name,
            per_person=allocated_to_item,
            total=item_total,
        ))
        for person, amount in allocated_to_item.items():
            per_person[person] = per_person.get(person, Decimal("0.00")) + amount

    per_person = {person: _money(amount) for person, amount in per_person.items()}
    if sum(per_person.values(), Decimal("0.00")) != calculated_total:
        raise ArithmeticError("Per-person item allocations do not add up to the calculated total.")
    if sum((row.total for row in item_allocations), Decimal("0.00")) != calculated_total:
        raise ArithmeticError("Item totals do not add up to the calculated total.")

    difference, reconciled = reconcile_total(calculated_total, bill.receipt_total)
    receipt = _money(bill.receipt_total) if bill.receipt_total is not None else None

    return SplitResult(
        subtotal=subtotal,
        service_charge=service_charge,
        gst=gst,
        calculated_total=calculated_total,
        receipt_total=receipt,
        difference=difference,
        reconciled=reconciled,
        per_person=per_person,
        item_allocations=item_allocations,
    )
