import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CLIReferenceTests(unittest.TestCase):
    def test_deployed_entrypoint_reads_persisted_orders_after_restart(self):
        with TemporaryDirectory() as folder:
            command = [sys.executable, str(ROOT / "app.py"), "--database", str(Path(folder) / "store.db")]
            def run(arguments):
                result = subprocess.run(command + arguments, check=True, capture_output=True, text=True, timeout=10)
                return json.loads(result.stdout)
            self.assertEqual({"orders": 0, "units": 0, "revenue_cents": 0}, run(["summary"]))
            self.assertEqual({"id": 1, "total_cents": 5000}, run(["checkout", "--quantity", "2"]))
            expected = {"orders": 1, "units": 2, "revenue_cents": 5000}
            self.assertEqual(expected, run(["summary"]))
            self.assertEqual(expected, run(["summary"]))
