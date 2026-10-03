"""Payments use case: charge an order. The only entry point other contexts may use."""
from decimal import Decimal
from uuid import uuid4

from payments.application.ports import PaymentStore
from payments.domain.payment import Payment


class ChargePayment:
    def __init__(self, payments: PaymentStore) -> None:
        self._payments = payments

    def execute(self, order_id: str, amount: Decimal) -> str:
        payment = Payment(reference=f"pay_{uuid4().hex[:12]}", order_id=order_id, amount=amount)
        return self._payments.insert_payment(payment.order_id, payment.amount, payment.reference)
