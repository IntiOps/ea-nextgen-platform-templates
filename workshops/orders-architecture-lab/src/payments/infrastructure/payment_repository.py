import sqlite3
from decimal import Decimal
from uuid import uuid4


class PaymentRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.execute("CREATE TABLE IF NOT EXISTS payments (reference TEXT PRIMARY KEY, order_id TEXT, amount TEXT)")

    def insert_payment(self, order_id: str, amount: Decimal, reference: str | None = None) -> str:
        reference = reference or f"pay_{uuid4().hex[:12]}"
        self._connection.execute("INSERT INTO payments VALUES (?, ?, ?)", (reference, order_id, str(amount)))
        return reference

    def count(self) -> int:
        return self._connection.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
