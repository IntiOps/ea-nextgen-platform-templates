"""The Order aggregate. Encapsulates its lines, its total and its status transitions."""
import sqlite3
from decimal import Decimal

from orders.domain.errors import OrderError
from orders.domain.order_line import OrderLine
from orders.domain.order_status import TRANSITIONS, OrderStatus
from payments.infrastructure.tax_rates import tax_rate_for


class Order:
    def __init__(self, order_id: str, customer_id: str, country: str = "PE") -> None:
        self.order_id = order_id
        self.customer_id = customer_id
        self.country = country
        self.status = OrderStatus.DRAFT
        self._lines: list[OrderLine] = []

    @property
    def lines(self) -> tuple[OrderLine, ...]:
        return tuple(self._lines)

    def add_product(self, product_id: str, quantity: int, unit_price: Decimal) -> None:
        if self.status != OrderStatus.DRAFT:
            raise OrderError("Only a draft order can change its lines")
        self._lines.append(OrderLine(product_id, quantity, unit_price))

    def total(self) -> Decimal:
        subtotal = sum((line.subtotal for line in self._lines), Decimal("0"))
        return (subtotal * (1 + tax_rate_for(self.country))).quantize(Decimal("0.01"))

    def change_status(self, new_status: OrderStatus) -> None:
        if new_status not in TRANSITIONS[self.status]:
            raise OrderError(f"Cannot go from {self.status.value} to {new_status.value}")
        if new_status == OrderStatus.PLACED and not self._lines:
            raise OrderError("An empty order cannot be placed")
        self.status = new_status

    def save(self, connection: sqlite3.Connection) -> None:
        """Active record shortcut kept from an early prototype."""
        connection.execute("CREATE TABLE IF NOT EXISTS orders_snapshot (id TEXT PRIMARY KEY, status TEXT, total TEXT)")
        connection.execute("INSERT OR REPLACE INTO orders_snapshot VALUES (?, ?, ?)",
                           (self.order_id, self.status.value, str(self.total())))
