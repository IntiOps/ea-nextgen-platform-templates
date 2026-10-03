"""Ports the Orders application needs from other contexts. Adapters live in infrastructure."""
from decimal import Decimal
from typing import Protocol


class PaymentGateway(Protocol):
    def charge(self, order_id: str, amount: Decimal) -> str:
        """Charge the amount and return the payment reference."""
        ...


class OrderNotifier(Protocol):
    def order_paid(self, order_id: str, customer_id: str) -> None: ...
