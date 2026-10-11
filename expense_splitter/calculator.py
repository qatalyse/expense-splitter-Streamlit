"""UI-independent bill calculation and allocation."""
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from .models import Bill, SplitResult
from .reconciliation import reconcile_total

_CENT = Decimal("0.01")

def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)

def _allocate_amount(amount: Decimal, weights: dict[str, Decimal]) -> dict[str, Decimal]:
    """Allocate charge cents proportional to original item shares."""
    if not weights:
        return {}
    denominator = sum(weights.values(), Decimal("0"))
    if denominator <= 0:
        return {person: Decimal("0.00") for person in weights}
    cents = int(_money(amount) * 100)
    exact = {person: Decimal(cents) * weight / denominator for person, weight in weights.items()}
    floors = {person: int(value.to_integral_value(rounding=ROUND_FLOOR)) for person, value in exact.items()}
    remaining = cents - sum(floors.values())
    ranked = sorted(exact, key=lambda person: exact[person] - floors[person], reverse=True)
    for person in ranked[:remaining]:
        floors[person] += 1
    return {person: Decimal(value) / 100 for person, value in floors.items()}

def split_expense(bill: Bill) -> SplitResult:
    """Calculate totals and per-person shares; receipt total is a checksum.

    MVP assumptions: service charge applies to subtotal; GST applies to subtotal
    plus service charge. Nett mode treats item prices as final. Discrepancies are
    reported and are never silently spread across participants.
    """
    if not bill.items:
        raise ValueError("Add at least one item.")
    item_shares: dict[str, Decimal] = {}
    subtotal = Decimal("0.00")
    for item in bill.items:
        if not item.name.strip():
            raise ValueError("Every item needs a name.")
        price = _money(item.price)
        if price < 0:
            raise ValueError(f"Item {item.name!r} cannot have a negative price.")
        participants = list(dict.fromkeys(p.strip() for p in item.participants if p.strip()))
        if not participants:
            raise ValueError(f"Assign at least one participant to {item.name!r}.")
        subtotal += price
        quotient, remainder = divmod(int(price * 100), len(participants))
        for index, person in enumerate(participants):
            cents = quotient + (1 if index < remainder else 0)
            item_shares[person] = item_shares.get(person, Decimal("0.00")) + Decimal(cents) / 100
    subtotal = _money(subtotal)
    rules = bill.billing
    if rules.prices_are_nett:
        service = Decimal("0.00")
        gst = Decimal("0.00")
    else:
        service = _money(subtotal * rules.service_charge_rate) if rules.service_charge_enabled else Decimal("0.00")
        gst_base = subtotal + service
        gst = _money(gst_base * rules.gst_rate) if rules.gst_enabled else Decimal("0.00")
    total = _money(subtotal + service + gst)
    shares = dict(item_shares)
    for adjustment in (service, gst):
        if adjustment:
            allocation = _allocate_amount(adjustment, item_shares)
            shares = {person: value + allocation.get(person, Decimal("0.00")) for person, value in shares.items()}
    shares = {person: _money(value) for person, value in shares.items()}
    if sum(shares.values(), Decimal("0.00")) != total:
        raise ArithmeticError("Per-person shares do not add up to the calculated total.")
    difference, reconciled = reconcile_total(total, bill.receipt_total)
    receipt = _money(bill.receipt_total) if bill.receipt_total is not None else None
    return SplitResult(subtotal, service, gst, total, receipt, difference, reconciled, shares)
