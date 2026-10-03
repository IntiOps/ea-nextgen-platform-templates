from decimal import Decimal
from typing import Protocol


class PaymentStore(Protocol):
    def insert_payment(self, order_id: str, amount: Decimal, reference: str | None = None) -> str: ...
