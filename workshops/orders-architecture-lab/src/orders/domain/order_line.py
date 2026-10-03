from dataclasses import dataclass
from decimal import Decimal

from orders.domain.errors import OrderError


@dataclass(frozen=True)
class OrderLine:
    product_id: str
    quantity: int
    unit_price: Decimal

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise OrderError("Quantity must be positive")
        if self.unit_price < 0:
            raise OrderError("Price cannot be negative")

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity
