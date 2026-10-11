"""Receipt checksum comparison."""
from decimal import Decimal

def reconcile_total(calculated_total: Decimal, receipt_total: Decimal | None, tolerance: Decimal = Decimal("0.01")) -> tuple[Decimal | None, bool | None]:
    """Return receipt-minus-calculated difference and a match flag."""
    if receipt_total is None:
        return None, None
    difference = (receipt_total - calculated_total).quantize(Decimal("0.01"))
    return difference, abs(difference) <= tolerance
