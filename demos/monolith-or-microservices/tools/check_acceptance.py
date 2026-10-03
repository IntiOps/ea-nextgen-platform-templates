"""Comprobación local del contrato; ejecutar desde una copia confiable para evaluar."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def main():
    problems = []
    forbidden = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*")
                 if p.name == "main.py" or p.name in {"services", "compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"}]
    if forbidden:
        problems.append("Artefactos incompatibles con el contrato de esta ronda: " + ", ".join(forbidden))
    if 'ENTRYPOINT ["python", "app.py"]' not in (ROOT / "Dockerfile").read_text():
        problems.append("El Dockerfile cambió el punto de entrada contratado")
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun < 5 or not result.wasSuccessful() or result.expectedFailures:
        problems.append("Se requieren al menos cinco tests correctos, sin fallas esperadas")
    with tempfile.TemporaryDirectory() as folder:
        base = [sys.executable, str(ROOT / "app.py"), "--database", str(Path(folder) / "store.db")]
        try:
            subprocess.run(base + ["checkout", "--quantity", "2"], check=True, capture_output=True, text=True, timeout=10)
            completed = subprocess.run(base + ["summary"], check=True, capture_output=True, text=True, timeout=10)
            if json.loads(completed.stdout) != {"orders": 1, "units": 2, "revenue_cents": 5000}:
                problems.append("El CLI real no devuelve el reporte esperado")
        except (subprocess.SubprocessError, ValueError) as error:
            problems.append("Falló el CLI real: " + str(error))
    for problem in problems:
        print("FAIL:", problem)
    if not problems:
        print("PASS: contrato local verificado; falta revisión humana del diff")
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
