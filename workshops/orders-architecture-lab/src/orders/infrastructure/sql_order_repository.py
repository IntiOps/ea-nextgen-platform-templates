"""Adapter: OrderRepository on SQLite. Infrastructure may depend on the domain, not the reverse."""
import sqlite3

from orders.domain.order import Order


class SqlOrderRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.execute("CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, customer TEXT, status TEXT)")
        self._cache: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._connection.execute("INSERT OR REPLACE INTO orders VALUES (?, ?, ?)",
                                 (order.order_id, order.customer_id, order.status.value))
        self._cache[order.order_id] = order

    def get(self, order_id: str) -> Order | None:
        return self._cache.get(order_id)
