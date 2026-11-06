"""Domain models for expense bills and detailed split results."""
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class Item:
    """The price is the item's total price, shared among participants."""
    name: str
    price: Decimal
    participants: list[str]


@dataclass(frozen=True)
class BillingRules:
    """Rates are fractions, e.g. Decimal("0.09") for 9 percent."""
    gst_enabled: bool = True
    gst_rate: Decimal = Decimal("0.09")
    service_charge_enabled: bool = True
    service_charge_rate: Decimal = Decimal("0.10")
    prices_are_nett: bool = False


@dataclass(frozen=True)
class Bill:
    items: list[Item]
    billing: BillingRules = field(default_factory=BillingRules)
    receipt_total: Decimal | None = None


@dataclass(frozen=True)
class ItemAllocation:
    """Final, charge-inclusive allocation of one receipt item."""
    item_name: str
    per_person: dict[str, Decimal]
    total: Decimal


@dataclass(frozen=True)
class SplitResult:
    subtotal: Decimal
    service_charge: Decimal
    gst: Decimal
    calculated_total: Decimal
    receipt_total: Decimal | None
    difference: Decimal | None
    reconciled: bool | None
    per_person: dict[str, Decimal]
    item_allocations: list[ItemAllocation]
