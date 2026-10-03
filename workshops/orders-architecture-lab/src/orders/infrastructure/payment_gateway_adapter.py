"""Adapter: the Orders PaymentGateway port, implemented through the Payments application layer.
This is the sanctioned way for Orders to reach Payments (ADR-0002)."""
from decimal import Decimal

from payments.application.charge import ChargePayment


class PaymentsApplicationGateway:
    def __init__(self, charge: ChargePayment) -> None:
        self._charge = charge

    def charge(self, order_id: str, amount: Decimal) -> str:
        return self._charge.execute(order_id, amount)
