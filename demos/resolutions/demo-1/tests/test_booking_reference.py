import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("booking_reference", ROOT / "app.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BookingReferenceTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.database = Path(folder.name) / "bookings.db"
        self.notifications = []
        self.app = module.BookingApp(self.database, self.notifications.append)
        self.request = {"request_id": "r-1", "event": "architecture-clinic", "seats": 1, "email": "demo@example.test"}

    def test_confirm_then_notify_once_and_retry_same_identity(self):
        first = self.app.book(self.request)
        self.assertEqual(100, first["total"])
        self.assertEqual(10000, first["total_cents"])
        self.assertEqual(first, self.app.receipt(first["id"]))
        self.assertEqual([], self.notifications)
        self.assertEqual(first, self.app.book(self.request))
        self.assertTrue(self.app.process_one(now=0))
        self.assertFalse(self.app.process_one(now=0))
        self.assertEqual([first], self.notifications)
        self.assertEqual("sent", self.app.delivery(first["id"])["state"])

    def test_capacity(self):
        self.app.book({**self.request, "seats": 2})
        with self.assertRaisesRegex(ValueError, "sold out"):
            self.app.book({**self.request, "request_id": "r-2"})

    def test_conflicting_identity(self):
        self.app.book(self.request)
        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.app.book({**self.request, "email": "other@example.test"})

    def test_invalid_quantity_has_no_side_effect(self):
        for seats in (-1, 0, True, 1.5, "1"):
            with self.subTest(seats=seats), self.assertRaises(ValueError):
                self.app.book({**self.request, "seats": seats})
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM bookings").fetchone()[0])
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])

    def test_price_snapshot(self):
        booking = self.app.book(self.request)
        self.app.prices[self.request["event"]] = 150.0
        self.assertEqual(booking, self.app.receipt(booking["id"]))

    def test_notification_failure_survives_restart_and_backoff(self):
        def unavailable(_):
            raise RuntimeError("offline")
        self.app.notify = unavailable
        booking = self.app.book(self.request)
        self.app.process_one(now=0)
        self.assertEqual(booking, self.app.receipt(booking["id"]))
        self.assertEqual("pending", self.app.delivery(booking["id"])["state"])
        restarted = module.BookingApp(self.database, self.notifications.append)
        self.assertFalse(restarted.process_one(now=1))
        self.assertTrue(restarted.process_one(now=2))
        self.assertEqual([booking], self.notifications)

    def test_failed_outbox_insert_rolls_back_booking(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("CREATE TRIGGER reject_outbox BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.app.book(self.request)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM bookings").fetchone()[0])

    def test_crash_after_send_can_duplicate_delivery(self):
        def crash_after_send(booking):
            self.notifications.append(booking)
            raise SystemExit("simulated worker crash")
        self.app.notify = crash_after_send
        booking = self.app.book(self.request)
        with self.assertRaises(SystemExit):
            self.app.process_one(now=0)
        restarted = module.BookingApp(self.database, self.notifications.append)
        self.assertFalse(restarted.process_one(now=29))
        self.assertTrue(restarted.process_one(now=30))
        self.assertEqual([booking, booking], self.notifications)
        self.assertEqual("sent", restarted.delivery(booking["id"])["state"])

    def test_retry_limit_requires_intervention(self):
        def unavailable(_):
            raise RuntimeError("offline")
        self.app.notify = unavailable
        booking = self.app.book(self.request)
        for now in (0, 2, 6, 14, 30):
            self.assertTrue(self.app.process_one(now=now))
        self.assertEqual("failed", self.app.delivery(booking["id"])["state"])
        self.assertEqual(5, self.app.delivery(booking["id"])["attempts"])
        self.assertFalse(self.app.process_one(now=100))

    def run_processes(self, identities):
        code = """import json, sys
from app import BookingApp
app = BookingApp(sys.argv[1], lambda b: None)
try:
    result = app.book(dict(request_id=sys.argv[2], event='architecture-clinic', seats=1, email='demo@example.test'))
    print(json.dumps(result))
except ValueError as error:
    print(json.dumps({'error': str(error)}))
"""
        processes = [subprocess.Popen([sys.executable, "-c", code, str(self.database), identity],
                     cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for identity in identities]
        results = []
        try:
            for process in processes:
                stdout, stderr = process.communicate(timeout=20)
                self.assertEqual(0, process.returncode, stderr)
                results.append(json.loads(stdout))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        return results

    def test_independent_processes_do_not_oversell(self):
        results = self.run_processes(["a", "b", "c", "d"])
        self.assertEqual(2, sum("id" in result for result in results))
        self.assertEqual(2, sum(result.get("error") == "sold out" for result in results))
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(2, connection.execute("SELECT SUM(seats) FROM bookings").fetchone()[0])

    def test_independent_processes_deduplicate_identity(self):
        results = self.run_processes(["same"] * 4)
        self.assertTrue(all(result == results[0] for result in results))
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM bookings").fetchone()[0])
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])
