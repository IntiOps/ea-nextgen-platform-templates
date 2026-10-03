"""Referencia local: reservas atómicas y notificaciones durables. Sin dependencias."""
from contextlib import closing, contextmanager
from decimal import Decimal
import json
import sqlite3
import time
import uuid


class BookingApp:
    def __init__(self, database, notify):
        self.database = str(database)
        self.notify = notify
        self.prices = {"architecture-clinic": 100.0}
        self.capacity = {"architecture-clinic": 2}
        with self.transaction() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
                event TEXT NOT NULL, seats INTEGER NOT NULL CHECK (seats > 0),
                email TEXT NOT NULL, total_cents INTEGER NOT NULL CHECK (total_cents >= 0)
            )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS outbox (
                booking_id INTEGER PRIMARY KEY REFERENCES bookings(id),
                state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                available_at REAL NOT NULL DEFAULT 0, lease_until REAL NOT NULL DEFAULT 0,
                token TEXT, last_error TEXT
            )""")

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.database, timeout=10)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                yield connection

    @staticmethod
    def view(row):
        booking = dict(row)
        # Compatibilidad de presentación; las operaciones monetarias usan centavos.
        booking["total"] = booking["total_cents"] / 100
        return booking

    def book(self, request):
        event, seats = request["event"], request["seats"]
        if type(seats) is not int or seats <= 0:
            raise ValueError("seats must be a positive integer")
        for key in ("request_id", "event", "email"):
            if not isinstance(request[key], str) or not request[key].strip():
                raise ValueError(f"{key} must be a nonempty string")
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM bookings WHERE request_id = ?", (request["request_id"],)
            ).fetchone()
            if existing:
                if any(existing[key] != request[key] for key in ("event", "seats", "email")):
                    raise ValueError("request_id conflicts with previous content")
                return self.view(existing)
            if event not in self.capacity or event not in self.prices:
                raise ValueError("unknown event")
            used = connection.execute(
                "SELECT COALESCE(SUM(seats), 0) FROM bookings WHERE event = ?", (event,)
            ).fetchone()[0]
            if used + seats > self.capacity[event]:
                raise ValueError("sold out")
            cents = Decimal(str(self.prices[event])) * 100
            if not cents.is_finite() or cents < 0 or cents != cents.to_integral_value():
                raise ValueError("price must be nonnegative with at most two decimal places")
            cursor = connection.execute(
                "INSERT INTO bookings (request_id, event, seats, email, total_cents) VALUES (?, ?, ?, ?, ?)",
                (request["request_id"], event, seats, request["email"], int(cents) * seats),
            )
            connection.execute("INSERT INTO outbox (booking_id) VALUES (?)", (cursor.lastrowid,))
            row = connection.execute("SELECT * FROM bookings WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return self.view(row)

    def receipt(self, booking_id):
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
            if row is None:
                raise ValueError("unknown booking")
            return self.view(row)

    def delivery(self, booking_id):
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM outbox WHERE booking_id = ?", (booking_id,)).fetchone()
            if row is None:
                raise ValueError("unknown booking")
            return dict(row)

    def process_one(self, now=None):
        """Un intento; lease de 30 s, backoff acotado y revisión manual tras 5 fallos.

        El adaptador debe tener timeout inferior al lease. No hay exactly-once externo.
        `now` permite probar recuperación sin esperas; en ejecución se usa el reloj real.
        """
        now = time.time() if now is None else now
        token = uuid.uuid4().hex
        with self.transaction() as connection:
            row = connection.execute("""SELECT * FROM outbox
                WHERE (state = 'pending' AND available_at <= ?)
                   OR (state = 'processing' AND lease_until <= ?)
                ORDER BY booking_id LIMIT 1""", (now, now)).fetchone()
            if row is None:
                return False
            booking_id, attempts = row["booking_id"], row["attempts"] + 1
            connection.execute("""UPDATE outbox SET state = 'processing', attempts = ?,
                token = ?, lease_until = ? WHERE booking_id = ?""",
                (attempts, token, now + 30, booking_id))
            booking = self.view(connection.execute(
                "SELECT * FROM bookings WHERE id = ?", (booking_id,)
            ).fetchone())
        # Fuera de la transacción de compra y de la que reclama trabajo.
        try:
            self.notify(booking)
        except Exception as error:
            state = "failed" if attempts >= 5 else "pending"
            with self.transaction() as connection:
                connection.execute("""UPDATE outbox SET state = ?, last_error = ?,
                    available_at = ?, token = NULL, lease_until = 0
                    WHERE booking_id = ? AND token = ?""",
                    (state, type(error).__name__, now + min(2 ** attempts, 60), booking_id, token))
        else:
            with self.transaction() as connection:
                connection.execute("""UPDATE outbox SET state = 'sent', last_error = NULL,
                    token = NULL, lease_until = 0 WHERE booking_id = ? AND token = ?""",
                    (booking_id, token))
        return True


if __name__ == "__main__":
    from pathlib import Path
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as folder:
        app = BookingApp(Path(folder) / "bookings.db", lambda b: print("Notification:", b["id"]))
        print(json.dumps(app.book({"request_id": "demo-1", "event": "architecture-clinic", "seats": 1, "email": "demo@example.test"})))
        app.process_one()
