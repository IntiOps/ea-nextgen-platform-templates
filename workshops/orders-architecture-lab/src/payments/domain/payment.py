from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Payment:
    reference: str
    order_id: str
    amount: Decimal
