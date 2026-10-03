"""Notifications use case, exposed to other contexts."""
from notifications.application.ports import MessageSender


class NotifyOrderPaid:
    def __init__(self, sender: MessageSender) -> None:
        self._sender = sender

    def order_paid(self, order_id: str, customer_id: str) -> None:
        self._sender.send(customer_id, f"Order {order_id} is paid")
