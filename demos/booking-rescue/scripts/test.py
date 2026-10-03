from pathlib import Path
import subprocess
import sys
from prepare import prepare

prepare()
raise SystemExit(subprocess.call(
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    cwd=Path(__file__).resolve().parents[1],
))
