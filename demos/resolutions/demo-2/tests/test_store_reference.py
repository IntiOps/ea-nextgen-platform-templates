import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("store_reference", Path(__file__).resolve().parents[1] / "app.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.store = module.Store(":memory:")
        self.addCleanup(self.store.close)

    def test_checkout(self):
        self.assertEqual({"id": 1, "total_cents": 5000}, self.store.checkout("book", 2))
        self.assertEqual(3, self.store.connection.execute("SELECT quantity FROM stock").fetchone()[0])

    def test_rejected_order_keeps_stock_and_orders(self):
        with self.assertRaises(ValueError):
            self.store.checkout("book", 6)
        self.assertEqual(5, self.store.connection.execute("SELECT quantity FROM stock").fetchone()[0])
        self.assertEqual(0, self.store.connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0])

    def test_order_write_failure_rolls_back_stock(self):
        self.store.connection.execute("CREATE TRIGGER reject_order BEFORE INSERT ON orders BEGIN SELECT RAISE(ABORT, 'simulated failure'); END")
        with self.assertRaises(module.sqlite3.IntegrityError):
            self.store.checkout("book", 1)
        self.assertEqual(5, self.store.connection.execute("SELECT quantity FROM stock").fetchone()[0])

    def test_empty_summary(self):
        self.assertEqual({"orders": 0, "units": 0, "revenue_cents": 0}, self.store.summary())

    def test_summary_reads_committed_orders_without_mutating_stock(self):
        self.store.checkout("book", 2)
        self.store.checkout("book", 1)
        expected = {"orders": 2, "units": 3, "revenue_cents": 7500}
        self.assertEqual(expected, self.store.summary())
        self.assertEqual(expected, self.store.summary())
        self.assertEqual(2, self.store.connection.execute("SELECT quantity FROM stock").fetchone()[0])
