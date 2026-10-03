"""Use case: place and pay an order."""
from decimal import Decimal

from orders.application.ports import OrderNotifier
from orders.domain.order import Order
from orders.domain.order_status import OrderStatus
from orders.domain.repository import OrderRepository
from payments.infrastructure.payment_repository import PaymentRepository


class PlaceOrder:
    def __init__(self, orders: OrderRepository, payments: PaymentRepository, notifier: OrderNotifier) -> None:
        self._orders = orders
        self._payments = payments
        self._notifier = notifier

    def execute(self, order_id: str, customer_id: str, lines: list[tuple[str, int, Decimal]]) -> Order:
        order = Order(order_id, customer_id)
        for product_id, quantity, unit_price in lines:
            order.add_product(product_id, quantity, unit_price)
        order.change_status(OrderStatus.PLACED)
        self._payments.insert_payment(order.order_id, order.total())
        order.change_status(OrderStatus.PAID)
        self._orders.save(order)
        self._notifier.order_paid(order.order_id, order.customer_id)
        return order
