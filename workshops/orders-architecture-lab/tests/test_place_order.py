import sqlite3
from decimal import Decimal

from notifications.application.notify import NotifyOrderPaid
from notifications.infrastructure.email_sender import EmailSender
from orders.application.place_order import PlaceOrder
from orders.domain.order_status import OrderStatus
from orders.infrastructure.sql_order_repository import SqlOrderRepository
from payments.infrastructure.payment_repository import PaymentRepository


def test_placing_an_order_charges_saves_and_notifies():
    connection = sqlite3.connect(":memory:")
    payments, sender = PaymentRepository(connection), EmailSender()
    orders = SqlOrderRepository(connection)
    order = PlaceOrder(orders, payments, NotifyOrderPaid(sender)).execute("o-1", "c-1", [("p-1", 2, Decimal("10"))])
    assert order.status == OrderStatus.PAID
    assert orders.get("o-1") is order
    assert payments.count() == 1
    assert sender.sent == [("c-1", "Order o-1 is paid")]
