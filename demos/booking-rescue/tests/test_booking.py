import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


spec = importlib.util.spec_from_file_location("booking_rescue_app", Path(__file__).resolve().parents[1] / "app.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
BookingApp = module.BookingApp


class BookingTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.database = Path(folder.name) / "bookings.json"
        self.notifications = []
        self.app = BookingApp(self.database, self.notifications.append)
        self.request = {"request_id": "r-1", "event": "architecture-clinic", "seats": 1, "email": "demo@example.test"}

    def test_happy_path(self):
        booking = self.app.book(self.request)
        self.assertEqual(100, booking["total"])
        self.assertEqual(booking, self.app.receipt(booking["id"]))
        self.assertEqual(1, len(self.notifications))

    def test_capacity(self):
        self.app.book({**self.request, "seats": 2})
        with self.assertRaisesRegex(ValueError, "sold out"):
            self.app.book({**self.request, "request_id": "r-2"})

    @unittest.expectedFailure
    def test_retry_returns_existing_booking(self):
        first = self.app.book(self.request)
        second = self.app.book(self.request)
        self.assertEqual(first, second)
        self.assertEqual(1, len(json.loads(self.database.read_text())))
        self.assertEqual(1, len(self.notifications))

    @unittest.expectedFailure
    def test_notification_failure_does_not_fail_committed_booking(self):
        def unavailable(_):
            raise RuntimeError("notification provider unavailable")
        self.app.notify = unavailable
        booking = self.app.book(self.request)
        self.assertEqual(booking, self.app.receipt(booking["id"]))

    @unittest.expectedFailure
    def test_receipt_keeps_agreed_price(self):
        booking = self.app.book(self.request)
        self.app.prices["architecture-clinic"] = 150.0
        self.assertEqual(booking["total"], self.app.receipt(booking["id"])["total"])

    @unittest.expectedFailure
    def test_negative_seats_rejected_without_writing(self):
        with self.assertRaises(ValueError):
            self.app.book({**self.request, "seats": -1})
        self.assertEqual([], json.loads(self.database.read_text()))
