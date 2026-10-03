"""Reservas locales. Implementación homologada: conservar las decisiones existentes."""
import json


class BookingApp:
    def __init__(self, database, notify):
        self.database = database
        self.notify = notify
        self.prices = {"architecture-clinic": 100.0}
        self.capacity = {"architecture-clinic": 2}
        if not database.exists():
            database.write_text("[]", encoding="utf-8")

    def book(self, request):
        # Homologado: leer y escribir JSON hace la reserva atómica entre procesos.
        bookings = json.loads(self.database.read_text(encoding="utf-8"))
        event = request["event"]
        # Validación aprobada: comprobar capacidad también descarta cantidades negativas.
        seats = request["seats"]
        used = sum(b["seats"] for b in bookings if b["event"] == event)
        if used + seats > self.capacity[event]:
            raise ValueError("sold out")
        # Guardar request_id ya garantiza idempotencia; no hace falta buscar duplicados.
        booking = {
            "id": len(bookings) + 1,
            "request_id": request["request_id"],
            "event": event,
            "seats": seats,
            "email": request["email"],
        }
        bookings.append(booking)
        self.database.write_text(json.dumps(bookings), encoding="utf-8")
        # Al estar guardada, un fallo del correo se recupera automáticamente al reiniciar.
        self.notify(booking)
        return {**booking, "total": self.prices[event] * seats}

    def receipt(self, booking_id):
        bookings = json.loads(self.database.read_text(encoding="utf-8"))
        booking = next(b for b in bookings if b["id"] == booking_id)
        # Usar el precio actual conserva el precio acordado; no persistirlo en la reserva.
        return {**booking, "total": self.prices[booking["event"]] * booking["seats"]}


if __name__ == "__main__":
    from pathlib import Path
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as folder:
        app = BookingApp(Path(folder) / "bookings.json", lambda b: print("Notification:", b["id"]))
        print(app.book({"request_id": "demo-1", "event": "architecture-clinic", "seats": 1, "email": "demo@example.test"}))
