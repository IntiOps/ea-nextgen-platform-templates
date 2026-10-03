"""Port: how the Orders domain expects orders to be stored. Implemented in infrastructure."""
from typing import Protocol

from orders.domain.order import Order


class OrderRepository(Protocol):
    def save(self, order: Order) -> None: ...

    def get(self, order_id: str) -> Order | None: ...
