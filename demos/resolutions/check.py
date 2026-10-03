"""Verifica las dos referencias ejecutables sin modificar las demos iniciales."""
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def main():
    failed = False
    for demo in ("demo-1", "demo-2"):
        print(f"Verificando {demo}", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=ROOT / demo,
        )
        failed = result.returncode != 0 or failed
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
